from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
import re
from datetime import datetime
import mysql.connector
from mysql.connector import FieldType
import connect

app = Flask(__name__)

dbconn = None
connection = None

def getCursor():
    global dbconn
    global connection
    connection = mysql.connector.connect(user=connect.dbuser, \
    password=connect.dbpass, host=connect.dbhost, \
    database=connect.dbname, autocommit=True)
    dbconn = connection.cursor(dictionary=True)
    return dbconn

@app.route("/")
def home():
    return redirect("/currentjobs")

# Generate the href based on field_value
def generate_href(field_value):
    return f'/job/{field_value}'

@app.route("/currentjobs")
def currentjobs():
    connection = getCursor()
    # add customers' name combine togther, add customer table for query
    connection.execute("SELECT a.job_id,a.customer,concat(ifnull(b.first_name,''),' ',ifnull(b.family_name,'')) customer_name,a.job_date FROM job a, customer b where a.completed=0 and a.customer=b.customer_id;")
    jobList = connection.fetchall()
    return render_template("currentjoblist.html", job_list = jobList, generate_href=generate_href)    

@app.route("/job/<int:job_id>", methods=['GET'])
def job_detail(job_id):
    connection = getCursor()
    
    # Fetch job details
    connection.execute("SELECT * FROM job WHERE job_id = %s", (job_id,))
    job = connection.fetchone()

    # From job_part, job and part table query the part usage of this job
    connection.execute("SELECT a.*, b.qty FROM part a JOIN job_part b ON a.part_id = b.part_id WHERE b.job_id = %s;", (job_id,))
    parts = connection.fetchall()

    # From job_service, service and job table query the service usage of this job
    connection.execute("SELECT a.*, b.qty FROM service a JOIN job_service b ON a.service_id = b.service_id WHERE b.job_id = %s", (job_id,))
    services = connection.fetchall()

    # Fetch lists of all available services and parts for adding to the job
    connection.execute("SELECT * FROM service")
    all_services = connection.fetchall()
    connection.execute("SELECT * FROM part")
    all_parts = connection.fetchall()

    part_costs = 0
    service_costs = 0
    for part in parts:
        part_costs += (part['qty'] * part['cost'])
    for service in services:
        service_costs += (service['qty'] * service['cost'])

    payload = (part_costs + service_costs, job_id)
    connection.execute("UPDATE job SET total_cost = %s where job_id = %s", payload)

    return render_template("job.html",
                           job=job,
                           services=services,
                           parts=parts,
                           all_services=all_services,
                           all_parts=all_parts)


@app.route("/job/<int:job_id>/add_part", methods=['POST'])
def add_part_to_job(job_id):
    connection = getCursor()

    part = request.form.get('part')
    qty = request.form.get('part_quantity')
    # Update database
    print(f"Part ID: {part}, Quantity: {qty}, Job ID: {job_id}")
    payload = (job_id, part, qty)
    connection.execute("INSERT INTO job_part (job_id, part_id, qty) VALUES (%s, %s, %s)", payload)

    return redirect(f"/job/{job_id}")


@app.route("/job/<int:job_id>/add_service", methods=['POST'])
def add_service_to_job(job_id):
    connection = getCursor()

    service = request.form.get('service')
    qty = request.form.get('service_quantity')

    # Update database
    print(f"Service ID: {service}, Quantity: {qty}, Job ID: {job_id}")
    payload = (job_id, service, qty)
    connection.execute("INSERT INTO job_service (job_id, service_id, qty) VALUES (%s, %s, %s)", payload)

    return redirect(f"/job/{job_id}")


@app.route("/job/<int:job_id>/complete_job", methods=['POST'])
def complete_job(job_id):
    connection = getCursor()
    # Update database
    print(f"Completing Job ID: {job_id}")
    payload = ("1", job_id)
    connection.execute("UPDATE job SET completed = %s where job_id = %s", payload)

    # Render the template with the form
    return redirect(f"/job/{job_id}")


@app.route("/admin", methods=['GET','POST'])
def admin():
    connection = getCursor()
    # cust_name = request.form.get('searchInput')
    cust_name = '' 
    cust_nmae_query = f"%{cust_name}%"
    cust_names = (cust_nmae_query, cust_nmae_query)

    connection.execute("select a.customer_id , ifnull(a.first_name,'') first_name, ifnull(a.family_name,'') family_name, a.email, a.phone from customer a where upper(trim(first_name)) like %s or upper(trim(family_name)) like %s", cust_names)
    customerList = connection.fetchall()

    connection.execute("SELECT a.job_id,concat(ifnull(b.first_name,''),' ',ifnull(b.family_name,'')) customer_name,a.job_date, a.paid FROM job a, customer b where a.paid=0 and a.customer=b.customer_id order by b.family_name, b.first_name, a.job_date;")
    unpaidList = connection.fetchall()

    connection.execute("select ifnull(b.family_name,'') family_name, ifnull(b.first_name,'') first_name, a.job_date, a.total_cost, case when a.completed=1 then 'Yes' else 'No' end completed, case when a.paid=1 then 'Yes' else 'No' end paid, case when datediff(curdate(), a.job_date) > 14 and a.completed = 1 and a.paid = 0 then 'Yes' else 'No' end overdue from job a, customer b where a.customer=b.customer_id order by b.family_name, b.first_name, a.job_date;")
    billList = connection.fetchall()

    if request.method == 'POST':
        cust_name = request.form.get('searchInput')
        cust_nmae_query = f"%{cust_name}%"
        cust_names = (cust_nmae_query, cust_nmae_query)

        connection.execute("select a.customer_id , ifnull(a.first_name,'') first_name, ifnull(a.family_name,'') family_name, a.email, a.phone from customer a where upper(trim(first_name)) like %s or upper(trim(family_name)) like %s", cust_names)
        customerList = connection.fetchall()

    return render_template("admin.html", customer_list = customerList, unpaid_list = unpaidList, bill_list=billList)

@app.route("/admin/add_cust", methods=['POST'])
def add_customer():
    connection = getCursor()
    connection.execute("select max(a.customer_id)+1 new_id from customer a;")
    cust_id = connection.fetchone()
    cust_id = cust_id['new_id']

    cust_first_name = request.form.get('customer_first_name')
    cust_family_name = request.form.get('customer_family_name')
    cust_email = request.form.get('customer_email')
    cust_phone = request.form.get('customer_phone')
    # Update database
    print(f"customer_id:{cust_id}, customer_first_name: {cust_first_name}, customer_last_name: {cust_family_name}, custmer_email: {cust_email}, customer_phone:{cust_phone}")
    # custload = (cust_id, cust_first_name, cust_family_name, cust_email,cust_phone)
    inster_stmt=("INSERT INTO customer (customer_id, first_name, family_name, email, phone) VALUES (%s, %s, %s, %s, %s)")
    data = (cust_id, cust_first_name, cust_family_name, cust_email,cust_phone)
    connection.execute(inster_stmt, data)
    # connection.close()

    return redirect("/admin")

if __name__ == '__main__':
    app.run()


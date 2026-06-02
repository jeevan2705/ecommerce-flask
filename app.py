from flask import Flask, make_response,request,url_for,redirect,render_template,flash,session,jsonify
from flask_session import Session
from io import BytesIO
from xhtml2pdf import pisa
from otp import genotp
from cmail import sendmail
from mysql.connector import (connection)
from stoken import endata,dndata
from werkzeug.utils import secure_filename #it checks wheater filename consists of extra / ,
from flask_bcrypt import Bcrypt
import re
import os
import razorpay
client=razorpay.Client(auth=("rzp_test_Sjy5hYBNuv6idu", "IHR2o3q89UEP4oZRQnzvxAtW"))
import pdfkit
mydb=connection.MySQLConnection(host=os.getenv("MYSQLHOST"),user=os.getenv("MYSQLUSER"),password=os.getenv("MYSQLPASSWORD"),database=os.getenv("MYSQLDATABASE"),port=int(os.getenv("MYSQLPORT")))
BASE_DIR=os.path.abspath(os.path.dirname(__file__)) # finds the exact path of app file directory
print(BASE_DIR)
UPLOAD_FOLDER=os.path.join(BASE_DIR,'static','uploads')
os.makedirs(UPLOAD_FOLDER,exist_ok=True)
ALLOWED_EXETENSIONS={'png','jpg','jpeg','gif','webp'}
MAX_CONTENT_LENGTH=6 *1024*1024 #6MB
app=Flask(__name__)
bcrypt=Bcrypt(app)
app.secret_key='Code2345'
app.config['SESSION_TYPE']='filesystem'
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH']=MAX_CONTENT_LENGTH
Session(app)
@app.route('/')
def home():
    return render_template('welcome.html')
@app.route('/index')
def index():
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items')
        allitems_data=cursor.fetchall()
        print(allitems_data)
        cursor.close()
    except Exception as e:
        print(e)
        flash('something Went wrong')
        return render_template('index.html')
    else:
        return render_template('index.html',allitems_data=allitems_data)
    
# ----   DEFINING ADMIN ROTES   ----

@app.route('/admincreate',methods=['GET','POST'])
def admincreate():
    if request.method=='POST':
        admin_username=request.form['name']
        admin_useremail=request.form['email']
        # admin_address=request.form['address']
        admin_password=request.form['password']
        # admin_agree=request.form['agree']
        admin_otp=genotp()
        admin_data={'admin_username':admin_username,'admin_useremail':admin_useremail,'admin_password':admin_password,'admin_otp':admin_otp}
        try:
            cursor=mydb.cursor(buffered=True)
            print("admincreate")
            cursor.execute('select count(*) from admindata where admin_email=%s',[admin_useremail])
            email_count=cursor.fetchone()[0] #(1,)
            cursor.close()
        except Exception as e:
            print(e)
            flash('something Went wrong')
            return redirect(url_for('admincreate'))
        else:
            if email_count==0:
                subject='OTP For Ecom23 verification'
                body=f"use the given otp for verification {admin_otp}"
                sendmail(to=admin_useremail,subject=subject,body=body)
                flash('OTP has been sent to the given mail')
                return redirect(url_for('adminotpverify',serverdata=endata(admin_data)))
            elif email_count==1:
                flash('Email already existed')
                return redirect(url_for('admincreate'))
            else:
                flash('No email found')
                return redirect(url_for('admincreate'))
    return render_template('admin_signup.html')


@app.route('/adminotpverify/<serverdata>',methods=['GET','POST'])
def adminotpverify(serverdata):
    if request.method=='POST':
        userotp = (
        request.form.get('otp1','') +
        request.form.get('otp2','') +
        request.form.get('otp3','') +
        request.form.get('otp4','') +
        request.form.get('otp5','') +
        request.form.get('otp6','')
)
        try:
            admin_data=dndata(serverdata)#{'admin_username':admin_username,'admin_useremail':admin_useremail,'admin_password':admin_password,'admin_address':admin_address,'adminagree':admin_agree,'admin_otp':admin_otp}
        except Exception as e:
            print(e)
            flash('Time out error')
            return redirect(url_for('admincreate'))
        else:
            if str(admin_data['admin_otp'])==str(userotp):
                print("otp verified")
                try:
                    hash_password=bcrypt.generate_password_hash(admin_data['admin_password'])
                    print(hash_password)
                    cursor=mydb.cursor(buffered=True)
                    print("Nothing")
                    cursor.execute('insert into admindata(adminid,admin_username,admin_email,admin_password) values(uuid_to_bin(uuid()),%s,%s,%s)',[admin_data['admin_username'],admin_data['admin_useremail'],hash_password])
                    mydb.commit()
                    cursor.close()   
                except Exception as e:
                    print(e)
                    flash('Could not store details')
                    return redirect(url_for('admincreate'))
                else:
                    flash('User registered successfully')
                    return redirect(url_for('adminlogin'))
            else:
                flash('Wrong otp')
                return redirect(url_for('adminotpverify',serverdata=serverdata))

    return render_template('adminotp.html')

@app.route('/adminforgotpwd',methods=['GET','POST'])
def adminforgotpwd():
    if request.method=='POST':
        email=request.form['email']
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select count(*) from admindata where admin_email=%s',[email])
            email_count=cursor.fetchone()[0] #(1,)
            cursor.close()
        except Exception as e:
            print(e)
            flash('something Went wrong')
            return redirect(url_for('adminforgotpwd'))
        else:
            if email_count==1:
                otp=genotp()
                subject='OTP For Ecom23 Admin Password Reset'
                body=f"use the given otp for password reset {otp}"
                sendmail(to=email,subject=subject,body=body)
                flash('OTP has been sent to the given mail')
                return redirect(url_for('adminforgotpwdotpverify',serverdata=endata({'email':email,'otp':otp})))
            elif email_count==0:
                flash('Email not found')
                return redirect(url_for('adminforgotpwd'))
            else:
                flash('No email found')
                return redirect(url_for('adminforgotpwd'))
    return render_template('adminforgotpwd.html')

@app.route('/resend_adminotp/<serverdata>')
def resend_adminotp(serverdata):
    try:
        admin_data=dndata(serverdata)
    except Exception as e:
        print(e)
        flash('Time out error')
        return redirect(url_for('admincreate'))
    else:
        admin_otp=genotp()
        admin_data['admin_otp']=admin_otp
        subject='OTP For Ecom23 verification'
        body=f"use the given otp for verification {admin_data['admin_otp']}"
        sendmail(to=admin_data['admin_useremail'],subject=subject,body=body)
        flash('OTP has been sent to the given mail')
        return redirect(url_for('adminotpverify',serverdata=endata(admin_data)))

@app.route('/adminlogin',methods=['GET','POST'])
def adminlogin():
    if request.method=='POST':
        login_email=request.form["email"]
        login_password=request.form['password']
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select count(*) from admindata where admin_email=%s',[login_email])
            email_count=cursor.fetchone() #(1,) or (0,) none
            cursor.close()
        except Exception as e:
            print(e)
            flash('Could not connect db')
            return redirect(url_for('adminlogin'))
        else:
            if email_count:
                if email_count[0]==1:
                    try:
                        cursor=mydb.cursor(buffered=True)
                        cursor.execute('select admin_password from admindata where admin_email=%s',[login_email])
                        stored_password=cursor.fetchone() #('fgjvjfj',)
                        if stored_password:
                            if bcrypt.check_password_hash(stored_password[0],login_password):
                                session['admin']=login_email
                                return redirect(url_for('admindashboard'))
                            else:
                                flash('Wrong password')
                                return redirect(url_for('adminlogin'))
                        else:
                            flash('could not verify password')
                            return redirect(url_for('adminlogin'))
                    except Exception as e:
                        print(e)
                        flash('Could not Verify password')
                        return redirect(url_for('adminlogin'))        
                elif email_count[0]==0:
                    flash('Email not found')
                    return redirect(url_for('adminlogin'))
            else:
                flash('Email Not registered')
                return redirect(url_for('adminlogin'))
    return render_template('admin_login.html')
@app.route('/admindashboard')
def admindashboard():
    if session.get('admin'):
        return render_template('adminpanel.html')
    else:
        flash('pls login to access dashboard')
        return redirect(url_for('adminlogin'))
def allowed_file(filename:str)->bool:
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXETENSIONS
@app.route('/additem',methods=['GET','POST'])
def additem():
    if session.get('admin'):
        if request.method=='POST':
            item_name=request.form['title']
            item_description=request.form['Description']
            item_about=request.form['About_item']
            item_cost=request.form['price']
            item_quantity=request.form['quantity']
            item_category=request.form['category']
            item_filedata=request.files['file']
            item_filename=item_filedata.filename
            print(item_filename)
            
            if item_filedata and item_filename:
                if not allowed_file(item_filename):
                    flash('File type not allowed: png,jpg,jpeg,webp,gif')
                    return redirect(url_for('additem'))
                orig_secure=secure_filename(item_filename)
                print(orig_secure)
                ext=os.path.splitext(orig_secure)[1]
                print(ext)
                filename=genotp()+ext
                save_path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                try:
                    item_filedata.save(save_path)
                except Exception as e:
                    print(e)
                    flash('could not save file')
                    return redirect(url_for('additem'))
            try:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('select adminid from admindata where admin_email=%s',[session.get('admin')])
                admin_id=cursor.fetchone()[0]
                cursor.execute('insert into items(itemid,itemname,item_description,item_about,item_price,item_quantity,item_category,filename,added_by) values(uuid_to_bin(uuid()),%s,%s,%s,%s,%s,%s,%s,%s)',[item_name,item_description,item_about,item_cost,item_quantity,item_category,filename,admin_id])
                mydb.commit()
                cursor.close()
            except Exception as e:
                print(e)
                if filename:
                    try:
                        os.remove(save_path)
                    except Exception as e:
                        print(e)
                        return redirect(url_for('additem'))
                flash('could not add item')
                return redirect(url_for('additem'))
            else:
                print("item added")
                flash('item successfully added')
                return redirect(url_for('additem'))

        return render_template('additem.html')
    else:
        flash('pls login to add item')
        return redirect(url_for('adminlogin'))
    
@app.route('/viewallitems')
def viewallitems():
    if session.get('admin'):
        print("view all items")
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select adminid from admindata where admin_email=%s',[session.get('admin')])
            admin_id=cursor.fetchone()
            if admin_id:
                cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where added_by=%s',[admin_id[0]])
                allitems_data=cursor.fetchall()
                cursor.close()
            else:
                flash('could not verify admin')
                return redirect(url_for('admindashboard'))
        except Exception as e:
            print(e)
            flash('could not get all items data')
            return redirect(url_for('admindashboard'))
        else:
            return render_template('viewallitems.html',allitems_data=allitems_data)
    else:
        flash('pls login to view items')
        return redirect(url_for('adminlogin'))
@app.route('/view_item/<itemid>')
def view_item(itemid):
    if session.get('admin'):
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select adminid from admindata where admin_email=%s',[session.get('admin')])
            admin_id=cursor.fetchone()[0]
            if admin_id:
                cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where added_by=%s and itemid=uuid_to_bin(%s)',[admin_id,itemid])
                item_data=cursor.fetchone()
                cursor.close()
            else:
                flash('Could not verify admin')
                return redirect(url_for('viewallitems'))
        except Exception as e:
            print(e)
            flash('Could not get item data')
            return redirect(url_for('viewallitems'))
        else:
            return render_template('viewitem.html',item_data=item_data)
    else:
        flash('pls login to view items')
        return redirect(url_for('adminlogin'))
@app.route('/deleteitem/<itemid>')
def deleteitem(itemid):
    if session.get('admin'):
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select adminid from admindata where admin_email=%s',[session.get('admin')])
            admin_id=cursor.fetchone()[0]
            if admin_id:
                cursor.execute('select filename from items where added_by=%s and itemid=uuid_to_bin(%s)',[admin_id,itemid])
                result=cursor.fetchone()

                if result:
                    filename=result[0]
                    cursor.execute('delete from items where added_by=%s and itemid=uuid_to_bin(%s)',[admin_id,itemid])
                    mydb.commit()

                    if filename:
                        file_path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            print(f"Error deleting file: {e}")
                    cursor.close()
                    flash('Item deleted successfully') 
                    return redirect(url_for('viewallitems'))
                else:
                    cursor.close()
                    flash('Item not found')
                    return redirect(url_for('viewallitems'))
            else:
                flash('Could not verify admin')
                return redirect(url_for('viewallitems'))
        except Exception as e:
            print(e)
            flash('Could not delete item')
            return redirect(url_for('viewallitems'))
    else:
        flash('pls login to delete items')
        return redirect(url_for('adminlogin'))
    
@app.route('/updateitem/<itemid>',methods=['GET','POST'])
def updateitem(itemid):
    if not session.get('admin'):
        flash('PLs login to updateitem')
        return redirect(url_for('adminlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select adminid from admindata where admin_email=%s',[session.get('admin')])
        admin_id=cursor.fetchone()
        if not admin_id:
            flash('Admin not verified')
            return redirect(url_for('viewallitems'))
        admin_data=admin_id[0]
        cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where added_by=%s and itemid=uuid_to_bin(%s)',[admin_data,itemid])
        storeditem_data=cursor.fetchone()

        if not storeditem_data:
            flash('Item details not found')
            return redirect(url_for('viewallitems'))
        filename=storeditem_data[7]
        old_filename=storeditem_data[7]
        cursor.close()
    except Exception as e:
        app.logger.exception(f'Could not fetch item data : {e}')
        flash('Could not find item')
        return redirect(url_for('viewallitems'))
    else:
        if request.method=='POST':
            print(request.form)
            updateditem_name=request.form['title']
            updateditem_description=request.form['Description']
            updateditem_about=request.form['About_item']
            updateditem_price=request.form['price']
            updateditem_quantity=request.form['quantity']
            updateditem_category=request.form['category']
            updateditem_filedata=request.files['file']
            print(updateditem_filedata)
            updateditem_filename=updateditem_filedata.filename
            new_file_path=None
            if updateditem_filedata and updateditem_filename:
                if not allowed_file(updateditem_filename):
                    flash('File type not allowed: png,jpg,jpeg,webp,gif')
                    return redirect(url_for('updateitem',itemid=itemid))
                orig_secure=secure_filename(updateditem_filename)
                ext=os.path.splitext(orig_secure)[1]
                filename=genotp()+ext
                new_file_path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                try:
                    updateditem_filedata.save(new_file_path)
                except Exception as e:
                    app.logger.exception(f'File save failed:{e}')
                    flash('could not save file')
                    return redirect(url_for('updateitem',itemid=itemid))
            #DB update
            try:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update items set itemname=%s,item_description=%s,item_about=%s,item_price=%s,item_quantity=%s,item_category=%s,filename=%s where added_by=%s and itemid=uuid_to_bin(%s)',[updateditem_name,updateditem_description,updateditem_about,updateditem_price,updateditem_quantity,updateditem_category,filename,admin_data,itemid])
                mydb.commit()
                cursor.close()
            except Exception as e:
                mydb.rollback()
                app.logger.exception(f'DB update failed:{e}')
                # remove newly uploaded file if db fails
                if new_file_path and os.path.exists(new_file_path):
                    os.remove(new_file_path)
                flash('Could not update item details')
                return redirect(url_for('updateitem',itemid=itemid))
            #After Db success --> delete old img
            else:
                if new_file_path and old_filename:
                    try:
                        old_path=os.path.join(app.config["UPLOAD_FOLDER"],old_filename)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        app.logger.warning(f'Old file delete failed :{e}')
                flash('Item Updated successfully')
                return redirect(url_for('viewallitems'))
        return render_template('updateitem.html',storeditem_data=storeditem_data)
@app.route('/adminprofileupdate',methods=['GET','POST'])
def adminprofileupdate():
    if not session.get('admin'):
        flash("pls login to view dashboard")
        return redirect(url_for('adminlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select adminid,admin_username,admin_phone,admin_address,admin_profileimg from admindata where admin_email=%s',[session.get('admin')])
        admin_data=cursor.fetchone() #(1,'anusha',null,'vij',null)
        if not admin_data:
            flash('Admin not verified')
            return redirect(url_for('admindashboard'))
        cursor.close()
    except Exception as e:
        app.logger.exception(f'Could not fetch admin data : {e}')
        flash('Could not find admin details')
        return redirect(url_for('admindashboard'))
    else:
        if request.method=='POST':
            updatedadmin_username=request.form['adminname']
            updatedadmin_address=request.form['address']
            updatedadmin_phone=request.form['ph_no'] #'None'
            updatedadmin_profileimg=request.files['file'] #''
            updatedadmin_filename=updatedadmin_profileimg.filename #anusha.jpg
            new_file_path=None
            filename=admin_data[4] #'null'
            old_filename=admin_data[4]
            if updatedadmin_phone=='None':
                updated_phone='0000000000'
            else:
                updated_phone=updatedadmin_phone
            if updatedadmin_profileimg and updatedadmin_filename:
                if not allowed_file(updatedadmin_filename):
                    flash('File type not allowed: png,jpg,jpeg,webp,gif')
                    return redirect(url_for('adminprofileupdate'))
                orig_secure=secure_filename(updatedadmin_filename)
                ext=os.path.splitext(orig_secure)[1] #.jpg
                filename=genotp()+ext #'D7gN8j.jpg'
                new_file_path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                try:
                    updatedadmin_profileimg.save(new_file_path)
                except Exception as e:
                    app.logger.exception(f'File save failed:{e}')
                    flash('could not save file')
                    return redirect(url_for('adminprofileupdate'))
            #DB update
            try:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update admindata set admin_username=%s,admin_address=%s,admin_profileimg=%s,admin_phone=%s  where admin_email=%s',[updatedadmin_username,updatedadmin_address,filename,updated_phone,session.get('admin')])
                mydb.commit()
                cursor.close()
            except Exception as e:
                mydb.rollback()
                app.logger.exception(f'DB update failed:{e}')
                # remove newly uploaded file if db fails
                if new_file_path and os.path.exists(new_file_path):
                    os.remove(new_file_path)
                flash('Could not update admin details')
                return redirect(url_for('adminprofileupdate'))
            #After Db success --> delete old img
            else:
                if new_file_path and old_filename:
                    try:
                        old_path=os.path.join(app.config["UPLOAD_FOLDER"],old_filename)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception as e:
                        app.logger.warning(f'Old file delete failed :{e}')
                flash('admin Updated successfully')
                return redirect(url_for('adminprofileupdate'))
    return render_template('adminupdate.html',admin_data=admin_data)
@app.route('/adminlogout')
def adminlogout():
    if not session.get('admin'):
        flash("pls login to view dashboard")
        return redirect(url_for('adminlogin'))
    else:
        session.pop('admin')
        return redirect(url_for('adminlogin'))

@app.route('/userlogout')
def userlogout():
    if not session.get('user'):
        flash("pls login to view dashboard")
        return redirect(url_for('userlogin'))
    else:
        session.pop('user')
        return redirect(url_for('userlogin'))


#defining user routes


@app.route('/usercreate',methods=['GET','POST'])
def usercreate():
    if request.method=='POST':
        username=request.form['name']
        useremail=request.form['email']
        useraddress=request.form['address']
        userpassword=request.form['password']
        usergender=request.form['usergender']
        userphoneno=request.form['phone_no']
        user_otp=genotp()
        user_data={'username':username,'useremail':useremail,'userpassword':userpassword,'useraddress':useraddress,'usergender':usergender,'userphone':userphoneno,'user_otp':user_otp}
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select count(*) from userdata where user_email=%s',[useremail])
            email_count=cursor.fetchone()[0] #(1,)
            cursor.close()
        except Exception as e:
            print(e)
            flash('something Went wrong')
            return redirect(url_for('usercreate'))
        else:
            if email_count==0:
                subject='OTP For Ecom23 verification'
                body=f"use the given otp for verification {user_otp}"
                sendmail(to=useremail,subject=subject,body=body)
                flash('OTP has been sent given mail')
                return redirect(url_for('userotpverify',serverdata=endata(user_data)))
            elif email_count==1:
                flash('Email already existed')
                return redirect(url_for('usercreate'))
            else:
                flash('No email found')
                return redirect(url_for('usercreate'))
    return render_template('usersignup.html') 
    

@app.route('/userotpverify/<serverdata>',methods=['GET','POST'])
def userotpverify(serverdata):
    if request.method=='POST':
        userotp=request.form['otp']
        try:
            user_data=dndata(serverdata)
        except Exception as e:
            print(e)
            flash('Time out error')
            return redirect(url_for('usercreate'))
        else:
            print("kjk")
            if user_data['user_otp']==userotp:
                print("otp verified")

                try:
                    hash_password=bcrypt.generate_password_hash(user_data['userpassword']).decode('utf-8')
                    cursor=mydb.cursor(buffered=True)
                    cursor.execute('insert into userdata(userid,username,user_email,address,gender,user_phone,password) values(uuid_to_bin(uuid()),%s,%s,%s,%s,%s,%s)',[user_data['username'],user_data['useremail'],user_data['useraddress'],user_data['usergender'],user_data['userphone'],hash_password])
                    mydb.commit()
                    cursor.close()   
                except Exception as e:
                    print(e)
                    flash('Could not store details')
                    return redirect(url_for('usercreate'))
                else:
                    flash('User registered successfully')
                    return redirect(url_for('userlogin'))
            else:
                flash('Wrong otp')
                return redirect(url_for('userotpverify',serverdata=serverdata))

    return render_template('userotp.html')

@app.route('/resend_userotp/<serverdata>')
def resend_userotp(serverdata):
    try:
        user_data=dndata(serverdata)
    except Exception as e:
        print(e)
        flash('Time out error')
        return redirect(url_for('usercreate'))
    else:
        user_otp=genotp()
        user_data['user_otp']=user_otp
        subject='OTP For Ecom23 verification'
        body=f"use the given otp for verification {user_data['user_otp']}"
        sendmail(to=user_data['useremail'],subject=subject,body=body)
        flash('OTP has been sent given mail')
        return redirect(url_for('userotpverify',serverdata=endata(user_data)))

@app.route('/userlogin',methods=['GET','POST'])
def userlogin():
    if request.method=='POST':
        login_email=request.form["email"]
        login_password=request.form['password']
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select count(*) from userdata where user_email=%s',[login_email])
            email_count=cursor.fetchone() #(1,) or (0,) none
            cursor.close()
        except Exception as e:
            print(e)
            flash('Could not connect db')
            return redirect(url_for('userlogin'))
        else:
            if email_count:
                if email_count[0]==1:
                    try:
                        cursor=mydb.cursor(buffered=True)
                        cursor.execute('select password from userdata where user_email=%s',[login_email])
                        stored_password=cursor.fetchone() #('fgjvjfj',)
                        if stored_password:
                            if bcrypt.check_password_hash(stored_password[0],login_password):
                                print(session)
                                session['user']=login_email
                                print(session,'user')
                                if not session.get(login_email):
                                    session[login_email]={}
                                print(session,'user cart session')
                                return redirect(url_for('userdashboard'))
                            else:
                                flash('Wrong password')
                                return redirect(url_for('userlogin'))
                        else:
                            flash(' password not found')
                            return redirect(url_for('userlogin'))
                    except Exception as e:
                        print(e)
                        flash('Could Verify password')
                        return redirect(url_for('userlogin'))        
                elif email_count[0]==0: 
                    flash('Email not found')
                    return redirect(url_for('userlogin'))
            else:
                flash('Email Not registered')
                return redirect(url_for('userlogin'))
    return render_template('userlogin.html')
@app.route('/userdashboard',methods=["GET"])
def userdashboard():
    if session.get('user'):
        try:
            cursor = mydb.cursor(buffered=True)
            cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items')
            allitems_data = cursor.fetchall()
            cursor.close()
        except Exception as e:
            print(e)
            flash('Could not load products')
            return render_template('userdashboard.html')
        else:
            return render_template('userdashboard.html', allitems_data=allitems_data)
    else:
        flash('pls login to access dashboard')
        return redirect(url_for('userlogin'))
@app.route('/addcart/<itemid>',methods=['GET'])
def addcart(itemid):
    if not session.get('user'):
        flash('pls login to addcart')
        return redirect(url_for('userlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where itemid=uuid_to_bin(%s)',[itemid])
        item_data=cursor.fetchone()
        cursor.close()
    except Exception as e:
        print(e)
        flash('Could not get item data')
        return redirect(url_for('index'))
    else:
        print(session)
        user = session.get('user')
        # allow optional quantity via query param
        try:
            qty = int(request.args.get('qty', 1))
        except Exception:
            qty = 1

        if user not in session or not isinstance(session.get(user), dict):
            session[user] = {}

        if itemid not in session[user]:
            session[user][itemid] = [item_data[1], qty, item_data[4], item_data[5], item_data[6], item_data[7]]
            session.modified = True
            flash('item added to cart')
        else:
            session[user][itemid][1] += qty
            session.modified = True
            flash('item quantity updated in cart')

        # if a next path is provided (e.g., return to user dashboard), redirect there
        next_path = request.args.get('next')
        if next_path and isinstance(next_path, str) and next_path.startswith('/'):
            return redirect(next_path)
        return redirect(url_for('viewcart'))



@app.route('/viewcart')
def viewcart():
    if not session.get('user'):
        flash('pls login to view cart')
        return redirect(url_for('userlogin'))
    try:
        user=session.get('user')
        items=session.get(user,{})
        print(items)
        items_total=0
        items_for_display=[]
        items_count=0
        for itemid,data in items.items():
            name=data[0]
            quantity=int(data[1])
            price=float(data[2])
            category=data[4] if len(data)>3 else None
            img=data[5] if len(data)>4 else None
            subtotal=price * quantity
            items_total += subtotal
            items_count += quantity
            items_for_display.append({
                'id': itemid,
                'name': name,
                'price': price,
                'quantity': quantity,
                'category': category,
                'imgname': img,
                'subtotal': subtotal
            })
        delivery=40
        tax=round(items_total * 0.05, 2)
        grand_total = items_total + delivery + tax
        return render_template(
            'cart.html',
            items_for_display=items_for_display,
            items_count=items_count,
            delivery=delivery,
            tax=tax,
            grand_total=grand_total,
            items_total=items_total
        )
    except Exception as e:
        print(e)
        flash('Could not get items details')
        return redirect(url_for('index'))
@app.route('/updatecart/<itemid>',methods=['POST'])
def updatecart(itemid):
    if not session.get('user'):
        flash('pls login to update cart')
        return redirect(url_for('userlogin'))
    try:
        updated_quantity=int(request.form['quantity'])
        if itemid in session[session.get('user')]:
            session[session.get('user')][itemid][1]=updated_quantity
            session.modified=True
            print(session)
            flash('item updated to cart')
            return redirect(url_for('viewcart'))
        else:
            flash('item not in  cart')
            return redirect(url_for('index'))
    except Exception as e:
        print(e)
        flash('Could not update cart item')
        return redirect(url_for('viewcart'))
@app.route('/removecart/<itemid>')
def removecart(itemid):
    if not session.get('user'):
        flash('pls login to update cart')
        return redirect(url_for('userlogin'))
    try:
        if itemid in session[session.get('user')]:
            session[session.get('user')].pop(itemid)
            session.modified=True
            print(session)
            flash('item removed from cart')
            return redirect(url_for('viewcart'))
        else:
            flash('item found in   cart')
            return redirect(url_for('index'))
    except Exception as e:
        print(e)
        flash('Could not remove cart item')
        return redirect(url_for('viewcart'))

@app.route('/category/<ctype>')
def category(ctype):
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where item_category=%s',[ctype])
        items_data=cursor.fetchall()
        if not items_data:
            flash('Item details not found')
            return redirect(url_for('index'))
    except Exception as e:
        app.logger.exception(f'Error fetching items:{e}')
        flash('Could not fetchthe item')
        return redirect(url_for('index'))
    else:
        return render_template('dashboard.html',items_data=items_data)
@app.route('/pay_cart',methods=['GET','POST'])
def pay_cart():
    if not session.get('user'):
        flash('pls login to pay cart')
        return redirect(url_for('userlogin'))
    try:
        #fetch all the cart items
        cart=session.get(session.get('user'),{})
        #only use single_buy if explicitly coming from buy now route
        cart_mode=''
        if request.args.get('type')=='single':
            cart=session.get('single_buy',{})
            cart_mode='single'
        else:
            if 'single_buy' in session:
                session.pop('single_buy')
                session.modified=True
                cart_mode='cart'
        if not cart:
            flash('Your cart is empty')
            return redirect(url_for('index'))
        items_total=0
        items_data=[]
        for itemid,data in cart.items():
            name=data[0]
            price=float(data[2])
            quantity=int(data[1])
            category=data[4] if len(data)>3 else None
            img=data[5] if len(data)>4 else None
            subtotal=price * quantity
            items_total +=subtotal
            items_data.append({
                'id':itemid,
                'name':name,
                'price':price,
                'quantity':quantity,
                'category':category,
                'imgname':img,
                'subtotal':subtotal
            })
        delivery=40
        tax=round(items_total*0.05,2)
        grand_total=int(items_total+delivery+tax)
        razorpay_amount=grand_total*100 #convert to paise
        #create razorpay order
        order=client.order.create({
            "amount":razorpay_amount,
            "currency":'INR',
            "receipt":f"{session.get('user')}",
            "payment_capture":"1"
        })
        print('created an order:',order)
        return render_template('pay.html',order=order,cart_items=items_data,items_total=items_total,delivery=delivery,tax=tax,grand_total=grand_total,cart_mode=cart_mode)
    except Exception as e:
        print('Could process payment :',e)
        flash('Payment failed')
        return redirect(url_for('viewcart'))
@app.route('/success_cart',methods=['POST'])
def success_cart():
    if not session.get('user'):
        flash('pls login')
        return redirect(url_for('userlogin'))
    try:
        payment_id=request.form['razorpay_payment_id']
        order_id=request.form['razorpay_order_id']
        signature=request.form['razorpay_signature']
        amount=float(request.form['grand_total'])
        mode=request.form['mode']
        #verify payment signature details
        param_dict={
            'razorpay_payment_id':payment_id,
            'razorpay_order_id':order_id,
            'razorpay_signature':signature
        }
        try:
            client.utility.verify_payment_signature(param_dict)
        except Exception as e:
            print(e)
            flash('Payment verification failed')
            return redirect(url_for('pay_cart'))
        if mode=='single':
            cart=session.get('single_buy',{})
        else:
            if 'single_buy' in session:
                session.pop('single_buy')
                session.modified=True
            cart=session.get(session.get('user'),{})
        if not cart:
            flash('Your cart is empty')
            return redirect(url_for('pay_cart'))
        items_total=sum(float(v[2]) * int(v[1]) for v in cart.values())
        delivery=40
        tax=round(items_total *0.05,2)
        grand_total=items_total+delivery+tax
        print(grand_total,amount,111)
        if int(amount)==int(grand_total):
            try:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('select userid from userdata where user_email=%s',[session.get('user')])
                user=cursor.fetchone()[0]
                cursor.execute('insert into orders(razorpay_orderid,razorpay_payment,userid,total_amount,delivery,tax,grand_total) values(%s,%s,%s,%s,%s,%s,%s)',[order_id,payment_id,user,items_total,delivery,tax,grand_total])
                order_table_id=cursor.lastrowid
                print(order_table_id,'rowid')
                insert_item='''insert into order_items(order_items_id,order_id,itemid,item_name, item_price,item_quantity,subtotal,item_category,filename) values(uuid_to_bin(uuid()),%s,uuid_to_bin(%s),%s,%s,%s,%s,%s,%s)'''
                for i,j in cart.items():
                    itemid=i
                    item_name=j[0]
                    item_quantity=int(j[1])
                    item_price=float(j[2])
                    category=j[4] if len(j)>4 else None
                    print(category,'hi')
                    img=j[5] if len(j)>5 else None
                    sub_total=item_price*item_quantity
                    cursor.execute(insert_item,[order_table_id,itemid,item_name,item_price,item_quantity,sub_total,category,img])
                mydb.commit()
                cursor.close()
            except Exception as e:
                app.logger.exception(f'Error order storage:{e}')
                flash('Could not store order details')
                return redirect(url_for('pay_cart'))
            #------- remove temp cart items
            if mode=='single':
                if 'single_buy' in session:
                    session.pop('single_buy')
                    session.modified=True
            session[session.get('user')]={}
            flash('Payment successful! Order placed.')
            return redirect(url_for('myorders'))
        else:
            print('Amount Failed')
            flash('Amount Invalid')
            return redirect(url_for('pay_cart'))
    except Exception as e:
        app.logger.exception(f'Error  verification failed:{e}')
        flash('Could not order.payment verification failed')
        return redirect(url_for('pay_cart'))
@app.route('/myorders')
def myorders():
    if not session.get('user'):
        flash('pls login to view orders')
        return redirect(url_for('userlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select userid from userdata where user_email=%s',[session.get('user')])
        user=cursor.fetchone()[0]
    except Exception as e:
        app.logger.exception('user not found')
        flash('could not verify user')
        return redirect(url_for('index'))
    else:
        if user:
            cursor.execute('select orderid,razorpay_orderid,razorpay_payment,userid,total_amount,delivery,tax,grand_total,created_at from orders where userid=%s order by created_at desc ',[user])
            order_data=cursor.fetchall()
            cursor.close()
            return render_template('myorders.html',order_data=order_data)
        else:
            flash('user not found')
            return redirect(url_for('index'))
@app.route('/myorder_details/<ordid>')
def myorder_details(ordid):
    if not session.get('user'):
        flash('pls login to view orders')
        return redirect(url_for('userlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select userid from userdata where user_email=%s',[session.get('user')])
        user=cursor.fetchone()[0]
    except Exception as e:
        app.logger.exception('user not found')
        flash('could not verify user')
        return redirect(url_for('index'))
    else:
        if user:
            try:
                cursor.execute('select orderid,razorpay_orderid,razorpay_payment,userid,total_amount,delivery,tax,grand_total,created_at from orders where userid=%s and orderid=%s ',[user,ordid])
                order_data=cursor.fetchone()
                cursor.execute('select order_items_id,order_id,bin_to_uuid(itemid),item_name,item_price,item_quantity,subtotal,item_category,filename from order_items where order_id=%s',[ordid])
                order_details=cursor.fetchall()
                cursor.close()
                return render_template('order_details.html',order_data=order_data,order_details=order_details)
            except Exception as e:
                app.logger.exception('could not fetch item details')
                flash('could not fetch item details')
                return redirect(url_for('index')) 
        else:
            flash('user not found')
            return redirect(url_for('myorders'))
@app.route('/get_invoice/<int:ord_id>')
def get_invoice(ord_id):
    if not session.get('user'):
        flash('pls login to view orders')
        return redirect(url_for('userlogin'))
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select userid from userdata where user_email=%s',[session.get('user')])
        user=cursor.fetchone()[0]
    except Exception as e:
        app.logger.exception('user not found')
        flash('could not verify user')
        return redirect(url_for('index'))
    else:
        if user:
            try:
                cursor.execute('select orderid,razorpay_orderid,razorpay_payment,userid,total_amount,delivery,tax,grand_total,created_at from orders where userid=%s and orderid=%s ',[user,ord_id])
                order_data=cursor.fetchone()
                cursor.execute('select order_items_id,order_id,bin_to_uuid(itemid),item_name,item_price,item_quantity,subtotal,item_category,filename from order_items where order_id=%s',[ord_id])
                order_details=cursor.fetchall()
                cursor.close()
                html=render_template('invoice.html',order_data=order_data,order_details=order_details)
                #generate pdf using wkhtmltopdf
                config=pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
                pdf=pdfkit.from_string(html,False,configuration=config)
                response=make_response(pdf)
                response.headers['Content-Type']='application/pdf'
                response.headers['Content-Disposition']=f'attachment; filename=invoice_{ord_id}.pdf'
                return response
            except Exception as e:
                app.logger.exception('could not fetch item details')
                flash('could not fetch item details')
                return redirect(url_for('index')) 
@app.route('/buy_now',methods=['POST'])
def buy_now():
    if not session.get('user'):
        flash('pls login to pay cart')
        return redirect(url_for('userlogin'))
    try:
        itemid=request.form['itemid']
        print(session)
        try:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where itemid=uuid_to_bin(%s)',[itemid])
            item_data=cursor.fetchone()
            cursor.close()
        except Exception as e:
            print(e)
            flash('Could not get item data')
            return redirect(url_for('index'))
        else:
            session['single_buy']={itemid:[item_data[1],1,item_data[4],item_data[5],item_data[6],item_data[7]]}
            session.modified=True
            print(session)
            flash('Item added to cart')
            return redirect(url_for('pay_cart',type='single'))
    except Exception as e:
            print(e)
            flash('Could not buy item')
            return redirect(url_for('index'))
@app.route('/desc_item/<itemid>')
def desc_item(itemid):
    try:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(itemid),itemname,item_description,item_about,item_price,item_quantity,item_category,filename from items where itemid=uuid_to_bin(%s)',[itemid])
        item_data=cursor.fetchone()
        cursor.close()
    except Exception as e:
        print(e)
        flash('Could not get item data')
        return redirect(url_for('index'))
    else:
        return render_template('desc.html',item_data=item_data)

app.run(debug=True,use_reloader=True)

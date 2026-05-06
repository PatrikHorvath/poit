from flask import Flask, render_template
import mysql.connector
import configparser

app = Flask(__name__)

import os

basedir = os.path.abspath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(basedir, "config.cfg"))

myhost = config.get("mysqlDB", "host")
myuser = config.get("mysqlDB", "user")
mypasswd = config.get("mysqlDB", "passwd")
mydb = config.get("mysqlDB", "db")


@app.route("/")
def hello_world():
    return "Hello, World!"


# predpriprava pre zapisaovanie a citanie dat do databazy
# aktualne uklada string data, neskor bude riesit pridanie
# jsonu s citanim senzorov do databazy
@app.route("/dbadd/<string:insert>")
def add(insert):
    db = mysql.connector.connect(
        host=myhost, user=myuser, password=mypasswd, database=mydb
    )
    cursor = db.cursor()

    cursor.execute("SELECT MAX(id) FROM prva")
    result = cursor.fetchone()

    maxid = result[0] if result[0] is not None else 0
    new_id = maxid + 1

    sql = "INSERT INTO prva (id, popis) VALUES (%s, %s)"
    cursor.execute(sql, (new_id, insert))

    db.commit()
    cursor.close()
    db.close()
    return "Done"


@app.route("/dbdata/<int:num>", methods=["GET", "POST"])
def dbdata(num):
    db = mysql.connector.connect(
        host=myhost, user=myuser, password=mypasswd, database=mydb
    )
    cursor = db.cursor()

    # Note: Use %s even for integers in mysql-connector
    cursor.execute("SELECT popis FROM prva WHERE id = %s", (num,))
    rv = cursor.fetchone()

    cursor.close()
    db.close()

    if rv:
        return str(rv[0])
    return "No record found", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

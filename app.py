from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "freshmart-demo-key"
DB = Path(__file__).with_name("freshmart.db")

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            category TEXT NOT NULL, price REAL NOT NULL, quantity INTEGER NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS sales(
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL, unit_price REAL NOT NULL, total REAL NOT NULL,
            sold_at TEXT NOT NULL)""")
        if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            con.executemany("INSERT INTO products(name,category,price,quantity) VALUES(?,?,?,?)", [
                ("Rice","Grains",60,30),("Wheat Flour","Grains",45,22),
                ("Milk","Dairy",30,8),("Apples","Fruits",120,6),
                ("Cooking Oil","Essentials",150,15),("Sugar","Essentials",44,4)])

@app.route("/")
def dashboard():
    with connect() as con:
        stats = {
            "products": con.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "units": con.execute("SELECT COALESCE(SUM(quantity),0) FROM products").fetchone()[0],
            "value": con.execute("SELECT COALESCE(SUM(price*quantity),0) FROM products").fetchone()[0],
            "low": con.execute("SELECT COUNT(*) FROM products WHERE quantity<=10").fetchone()[0],
            "sales": con.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0]
        }
        products = con.execute("SELECT * FROM products ORDER BY name").fetchall()
        alerts = con.execute("SELECT * FROM products WHERE quantity<=10 ORDER BY quantity").fetchall()
        recent = con.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, products=products, alerts=alerts, recent=recent)

@app.route("/inventory")
def inventory():
    q = request.args.get("q","").strip()
    with connect() as con:
        products = con.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY name",
                               (f"%{q}%", f"%{q}%")).fetchall()
    return render_template("inventory.html", products=products, q=q)

@app.route("/add", methods=["POST"])
def add():
    try:
        name=request.form["name"].strip(); category=request.form["category"].strip()
        price=float(request.form["price"]); quantity=int(request.form["quantity"])
        if not name or not category or price < 0 or quantity < 0: raise ValueError
    except (ValueError, KeyError):
        flash("Enter valid product details.", "error")
        return redirect(url_for("dashboard")+"#add-product")
    with connect() as con:
        con.execute("INSERT INTO products(name,category,price,quantity) VALUES(?,?,?,?)",
                    (name,category,price,quantity))
    flash("Product added successfully.", "success")
    return redirect(url_for("inventory"))

@app.route("/edit/<int:pid>", methods=["GET","POST"])
def edit(pid):
    with connect() as con:
        product=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
        if product is None:
            flash("Product not found.", "error"); return redirect(url_for("inventory"))
        if request.method=="POST":
            try:
                name=request.form["name"].strip(); category=request.form["category"].strip()
                price=float(request.form["price"]); quantity=int(request.form["quantity"])
                if not name or not category or price<0 or quantity<0: raise ValueError
            except (ValueError,KeyError):
                flash("Enter valid details.", "error")
                return render_template("edit.html", product=product)
            con.execute("UPDATE products SET name=?,category=?,price=?,quantity=? WHERE id=?",
                        (name,category,price,quantity,pid))
            flash("Product updated.", "success"); return redirect(url_for("inventory"))
    return render_template("edit.html", product=product)

@app.route("/delete/<int:pid>", methods=["POST"])
def delete(pid):
    with connect() as con: con.execute("DELETE FROM products WHERE id=?",(pid,))
    flash("Product deleted.", "success")
    return redirect(url_for("inventory"))

@app.route("/billing", methods=["GET","POST"])
def billing():
    with connect() as con:
        products=con.execute("SELECT * FROM products WHERE quantity>0 ORDER BY name").fetchall()
        if request.method=="POST":
            try:
                pid=int(request.form["product_id"]); qty=int(request.form["quantity"])
                p=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
                if p is None or qty<=0: raise ValueError
                if qty>p["quantity"]:
                    flash(f"Only {p['quantity']} unit(s) available.", "error")
                    return redirect(url_for("billing"))
                total=round(p["price"]*qty,2)
                con.execute("UPDATE products SET quantity=quantity-? WHERE id=?",(qty,pid))
                con.execute("INSERT INTO sales(product_name,quantity,unit_price,total,sold_at) VALUES(?,?,?,?,?)",
                            (p["name"],qty,p["price"],total,datetime.now().strftime("%Y-%m-%d %H:%M")))
                flash(f"Bill created. Total: ₹{total:.2f}", "success")
                return redirect(url_for("sales"))
            except (ValueError,KeyError):
                flash("Choose a product and valid quantity.", "error")
    return render_template("billing.html", products=products)

@app.route("/sales")
def sales():
    with connect() as con:
        rows=con.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
        total=con.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0]
    return render_template("sales.html", sales=rows, total=total)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)

from flask import Flask, request, render_template, redirect, url_for
from pymongo import MongoClient
from bson.objectid import ObjectId

# Setup Flask app.
app = Flask(__name__)

# Setup MongoDB client.
client = MongoClient('localhost', 27017)  # Connect to local MongoDB instance.
db = client['__wiki__']  # Use (or create) a database called '__wiki__'.
pages = db['pages']  # Use (or create) a collection called 'pages'.

@app.route('/')
def home():
    page_data = pages.find()
    return render_template('home.html.jinja', pages=page_data)

@app.route('/page/<page_id>')
def page(page_id):
    page_data = pages.find_one({'_id': ObjectId(page_id)})
    return render_template('page.html.jinja', page=page_data)

@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        pages.insert_one({'title': title, 'content': content})
        return redirect(url_for('home'))
    return render_template('create.html.jinja')

@app.route('/edit/<page_id>', methods=['GET', 'POST'])
def edit(page_id):
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        pages.update_one({'_id': ObjectId(page_id)}, {'$set': {'title': title, 'content': content}})
        return redirect(url_for('page', page_id=page_id))
    page_data = pages.find_one({'_id': ObjectId(page_id)})
    return render_template('edit.html.jinja', page=page_data)

if __name__ == '__main__':
    app.run(debug=True)
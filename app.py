from flask import Flask, request, render_template, redirect, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import markdown

def parse_content_as_markdown(content):
    return markdown.markdown(content)

def read_yaml_config(filename):
    config = {}
    with open(filename, 'r') as file:
        for line in file:
            # Remove newline character
            line = line.rstrip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Split line into key and value
            key, value = line.split(':', 1)

            # Remove leading and trailing whitespace
            key = key.strip()
            value = value.strip()

            # Convert to boolean if needed
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False

            config[key] = value

    return config

# import the config file
config = read_yaml_config('config.yaml')

# Setup Flask app.
app = Flask(__name__)
app.config.update(config)

# Setup MongoDB client.
client = MongoClient('localhost', 27017)  # Connect to local MongoDB instance.
db = client['__wiki__']  # Use (or create) a database called '__wiki__'.
pages = db['pages']  # Use (or create) a collection called 'pages'.

@app.route('/')
def home():
    return render_template('home.html.jinja', pages=pages.find())

@app.route('/page/<page_id>')
def page(page_id):
    page_data = pages.find_one({'_id': ObjectId(page_id)})
    page_data['content'] = parse_content_as_markdown(page_data['content'])
    return render_template('page.html.jinja', page=page_data, pages=pages.find())


@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        pages.insert_one({'title': title, 'content': content})
        return redirect(url_for('home'))
    return render_template('create.html.jinja', pages=pages.find())

@app.route('/edit/<page_id>', methods=['GET', 'POST'])
def edit(page_id):
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        pages.update_one({'_id': ObjectId(page_id)}, {'$set': {'title': title, 'content': content}})
        return redirect(url_for('page', page_id=page_id))
    page_data = pages.find_one({'_id': ObjectId(page_id)})
    return render_template('edit.html.jinja', page=page_data, pages=pages.find())

@app.route('/render_md', methods=['POST'])
def render_md():
    content = request.get_json()['content']
    html_content = parse_content_as_markdown(content)
    return jsonify({'content': html_content})

if __name__ == '__main__':
    app.run(debug=True)
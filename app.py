from flask import Flask, request, render_template, redirect, url_for, jsonify, send_from_directory
from pymongo import MongoClient
from bson.objectid import ObjectId
import markdown
import os

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

class MongoDocument:
    def __init__(self, host='localhost', port=27017, db_name='__wiki__', collection_name='pages', trash_name='trash'):
        client = MongoClient(host, port)
        db = client[db_name]
        self.collection = db[collection_name]
        self.trash = db[trash_name]

    def create(self, data):
        return self.collection.insert_one(data).inserted_id

    def find_one(self, document_id):
        return self.collection.find_one({'_id': ObjectId(document_id)})


    def update_one(self, document_id, data):
        return self.collection.update_one({'_id': ObjectId(document_id)}, {'$set': data})

    def delete(self, document_id):
        document = self.read(document_id)
        if document:
            self.trash.insert_one(document)
            self.collection.delete_one({'_id': ObjectId(document_id)})

    def restore(self, document_id):
        document = self.trash.find_one({'_id': ObjectId(document_id)})
        if document:
            self.collection.insert_one(document)
            self.trash.delete_one({'_id': ObjectId(document_id)})

    def find(self, query={}):
        return self.collection.find(query)

# Setup MongoDocuent object.
pages = MongoDocument('localhost', 27017, '__wiki__', 'pages')


# Setup Flask app.
app = Flask(__name__)
app.config.update(config)
app.static_folder = 'static/'


@app.route('/')
def home():
    return render_template('home.html.jinja', pages=pages.find())

@app.route('/page/<page_id>')
def page(page_id):
    page_data = pages.find_one(page_id)
    page_data['content'] = parse_content_as_markdown(page_data['content'])
    return render_template('page.html.jinja', page=page_data, pages=pages.find(), page_id=page_id)


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
        pages.update_one(page_id, {'title': title, 'content': content})
        return redirect(url_for('page', page_id=page_id))
    page_data = pages.find_one(page_id)
    return render_template('edit.html.jinja', page=page_data, pages=pages.find(), page_id=page_id)

# restfully render content as markdown
@app.route('/render_md', methods=['POST'])
def render_md():
    content = request.get_json()['content']
    html_content = parse_content_as_markdown(content)
    return jsonify({'content': html_content})

#######################
# REST API Routes
#######################

# API documentation
@app.route('/docs/api')
def api_docs():
    return render_template('docs_api.html.jinja', pages=pages.find())


@app.route('/api/<page_name>', methods=['GET'])
def api_get(page_name):
    page_id = ObjectId(page_name)  # Convert the page_name into ObjectId
    page_data = pages.find_one(page_id)  # Fetch the page from MongoDB
    if page_data:
        return jsonify(page_data), 200
    else:
        return jsonify({"error": "Page not found"}), 404


@app.route('/api/<page_name>', methods=['POST'])
def api_post(page_name):
    new_data = request.json  # Get the new data from the request
    result = pages.update_one(ObjectId(page_name), new_data)  # Update the page with the new data
    if result.matched_count > 0:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Page not found"}), 404


@app.route('/api/<page_name>', methods=['DELETE'])
def api_delete(page_name):
    pages.delete(ObjectId(page_name))  # Delete the page
    return jsonify({"success": True}), 200


@app.route('/api', methods=['POST'])
def api_create():
    new_data = request.json  # Get the new data from the request
    new_id = pages.create(new_data)  # Create a new page with the new data
    return jsonify({"_id": str(new_id)}), 201


@app.route('/api', methods=['GET'])
def api_get_all():
    all_pages = list(pages.find())  # Fetch all pages from MongoDB
    for page in all_pages:
        page["_id"] = str(page["_id"])  # Convert ObjectId to string for JSON serialization
    return jsonify(all_pages), 200

#######################
# Look-and-feel Routes
#######################

# add a route to the favicon
@app.route('/favicon.ico')
def site_favicon():
    directory_path, file_name = os.path.split(app.config['favicon'])
    return send_from_directory(directory_path, file_name)

# add a route to the site logo
@app.route('/site_logo')
def site_logo():
    if app.config['site_logo']:
        directory_path, file_name = os.path.split(app.config['site_logo'])
        return send_from_directory(directory_path, file_name, mimetype="image/vnd.microsoft.icon")
    return abort(404)




if __name__ == '__main__':
    app.run(debug=True)
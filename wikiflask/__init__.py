"""
wiki-flask.py

"""


__name__="wikiflask"
__author__ = "Sig Janoska-Bedi"
__credits__ = ["Sig Janoska-Bedi"]
__version__ = "0.3.0"
__license__ = "AGPL-3.0"
__maintainer__ = "Sig Janoska-Bedi"
__email__ = "signe@atreeus.com"


from flask import Flask, request, render_template, redirect, url_for, jsonify, send_from_directory, send_file, flash, abort
from pymongo import MongoClient
from bson.objectid import ObjectId
import markdown
import os
import yaml
import uuid
import datetime
from num2words import num2words
import difflib
from xhtml2pdf import pisa
from io import BytesIO
# from urllib.parse import quote
import re
from gtts import gTTS
from multiprocessing import Process, Manager
import json
from tempfile import TemporaryDirectory

def prettify_time_diff(dt, anchor=datetime.datetime.now()):

    delta = anchor - dt

    if delta < datetime.timedelta(minutes=1):
        return 'just now'
    elif delta < datetime.timedelta(hours=1):
        minutes = delta.seconds // 60
        return f'{num2words(minutes)} minute{"s" if minutes != 1 else ""} ago'
    elif delta < datetime.timedelta(days=1):
        hours = delta.seconds // 3600
        return f'{num2words(hours)} hour{"s" if hours != 1 else ""} ago'
    else:
        days = delta.days
        return f'{num2words(days)} day{"s" if days != 1 else ""} ago'


# Create the audio directory if it doesn't exist
directory = os.path.join('wikiflask', 'static', 'audio')
if not os.path.exists(directory):
    os.makedirs(directory)


# Create a Manager to share state between processes
manager = Manager()

# This dict will store currently running processes
running_processes = manager.dict()


def generate_audio_from_text(document_id, document_content):
    tts = gTTS(text=document_content, lang='en')  # Create a gTTS object

    # Save to an .mp3 file
    audio_path = os.path.join(directory, f'{str(document_id)}.mp3')
    tts.save(audio_path)

def set_secret_key():
    # Check if the secret key file exists
    if os.path.exists('.secret_key'):
        # If it exists, read the key from the file
        with open('.secret_key', 'r') as f:
            secret_key = f.read()
    else:
        # If it doesn't exist, generate a new UUID and save it in the file
        secret_key = str(uuid.uuid4())
        with open('.secret_key', 'w') as f:
            f.write(secret_key)
    return secret_key


def parse_content_as_markdown(content):
    return markdown.markdown(content)

# Load config.yaml if it exists
if os.path.exists('config.yaml'):
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
else:
    config = {}

# Load default_config.yaml
with open('default_config.yaml', 'r') as f:
    default_config = yaml.safe_load(f)

# Append fields from default_config.yaml that are not set in config.yaml
for key, value in default_config.items():
    if key not in config:
        config[key] = value

class MongoDocument:
    def __init__(self, host='localhost', port=27017, user=None, pw=None, db_name='__wiki__', collection_name='pages', trash_name='trash', backups_name="backups"):

        if user and pw:
            client = MongoClient(host, port, username=user, password=pw)
        else:
            client = MongoClient(host, port)

        db = client[db_name]
        self.collection = db[collection_name]
        self.trash = db[trash_name]
        self.backups = db[backups_name]
        

        # update index index
        # self.index()

    def create(self, data, parent_id=None):
        data['created_at'] = datetime.datetime.now()
        data['last_edited'] = datetime.datetime.now()
        data['bookmarked'] = False # by default, we do not bookmark files
        data['tags'] = data['tags'] if 'tags' in data else [] # by default, we add an empty list of tags
        
        if parent_id is not None:
            # It's a child page - position is next highest among its siblings
            data['parent_id'] = parent_id
            data['position'] = self.collection.count_documents({'parent_id': parent_id}) + 1
        else:
            # It's a top-level page - position is next highest among top-level pages
            data['position'] = self.collection.count_documents({'parent_id': None}) + 1

        # adding a url-safe title
        # data['urlsafe_title'] = quote(data['title']) 
        data['urlsafe_title'] = re.sub("[^a-z0-9-]", "", data['title'].lower().replace(" ", "-"))
        # print(data['urlsafe_title'])

        document_id = self.collection.insert_one(data).inserted_id

        return document_id


    def find_one(self, document_id):
        return self.collection.find_one({'_id': ObjectId(document_id)})

    def get_page_with_children(self, page_id):
        page = self.find_one(page_id)
        if page is not None:
            children = self.collection.find({'parent_id': page_id})
            page['children'] = list(children)
        return page

    def toggle_bookmark(self, document_id, bookmark:bool):
        # Get the current version of the document
        current_document = self.find_one(document_id)

        if current_document is None:
            raise ValueError(f"No document with ID {document_id} exists in the collection.")

        # Update the 'bookmarked' field
        return self.collection.update_one({'_id': ObjectId(document_id)}, {'$set': {'bookmarked': bookmark}})

    def update_one(self, document_id, data, parent_id=None):

        # Get the current version of the document
        current_document = self.find_one(document_id)

        if current_document is None:
            raise ValueError(f"No document with ID {document_id} exists in the collection.")

        # Backup the current version
        backup_document = current_document.copy()
        backup_document['old_id'] = backup_document['_id']
        del backup_document['_id'] # Remove old id to let MongoDB generate a new one
        self.backups.insert_one(backup_document)

        # Update the document
        data['last_edited'] = datetime.datetime.now()

        update_ops = {"$set": data}

        if parent_id is not None:
            data['parent_id'] = parent_id
        else:
            # If parent_id is None, prepare to unset it
            update_ops["$unset"] = {"parent_id": ""}

        # adding a url-safe title
        # data['urlsafe_title'] = quote(data['title'])
        data['urlsafe_title'] = re.sub("[^a-z0-9-]", "", data['title'].lower().replace(" ", "-"))
        # print(data['urlsafe_title'])

        self.collection.update_one({'_id': ObjectId(document_id)}, update_ops)

        return current_document['_id']

    def is_parent(self, document_id):
        query = {'parent_id': document_id}
        c = self.collection.count_documents(query)
        # if c == 0:
        #     print(f"No documents found with parent_id = {document_id}")
        #     print("Query was:", query)
        # else:
        #     print(f"Found {c} documents with parent_id = {document_id}")
        return c > 0


    def delete(self, document_id):
        document = self.find_one(document_id)
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

    def find_trash(self, query={}):
        return self.trash.find(query)

    def find_backups(self, query={}):
        return self.backups.find(query)

    def find_trash(self, query={}):
        return self.trash.find(query)

    def index(self):
        self.collection.create_index([("title", "text"), ("content", "text")], default_language='english')


    def update_positions(self, _id, new_position):
        # Get the old position of the page
        page_data = self.collection.find_one({"_id": _id})
        old_position = page_data['position']
        
        if old_position < new_position:
            # If moving down, decrement positions of in-between pages
            self.collection.update_many(
                {"position": {"$gt": old_position, "$lt": new_position}},
                {"$inc": {"position": -1}}
            )
        else:
            # If moving up, increment positions of in-between pages
            self.collection.update_many(
                {"position": {"$lt": old_position, "$gt": new_position}},
                {"$inc": {"position": 1}}
            )

        # Finally, update the position of the moved page
        self.collection.update_one(
            {"_id": _id},
            {"$set": {"position": new_position}}
        )


    def restore_from_backup(self, backup_id):
        # Find the document from the backups
        backup_document = self.backups.find_one({'_id': ObjectId(backup_id)})

        if backup_document:
            # Get the original ID
            document_id = str(backup_document['old_id'])

            # Save the current version to backups
            _ = self.collection.find_one({'_id': ObjectId(document_id)})
            current_document = _.copy()
            current_document['old_id'] = current_document['_id']
            del current_document['_id']  # Remove old id to let MongoDB generate a new one
            self.backups.insert_one(current_document)

            # Remove the _id fields from the backup document
            del backup_document['_id']
            del backup_document['old_id']

            # Replace the document with the restored version
            self.collection.replace_one({'_id': ObjectId(document_id)}, backup_document)

            # Remove the restored version from the backups
            self.backups.delete_one({'_id': ObjectId(backup_id)})
        else:
            raise ValueError(f"No backup with ID {backup_id} exists in the backups.")

def breadcrumb(page, pages):
    breadcrumb_pages = []
    while page:
        breadcrumb_pages.append(page)
        parent_id = page.get('parent_id')
        if parent_id is not None:
            # find the parent page by its ObjectId
            page = next((p for p in pages if p['_id'] == ObjectId(parent_id)), None)
        else:
            # no parent_id means we've reached the top, so break the loop
            break
    return breadcrumb_pages[::-1]

# Setup Flask app.
app = Flask(__name__)
app.config.update(config)
app.static_folder = 'static/'
app.jinja_env.filters['zip'] = zip
app.jinja_env.globals.update(breadcrumb=breadcrumb)
app.jinja_env.add_extension('jinja2.ext.do')
app.secret_key = set_secret_key()

# Setup MongoDocuent object.
pages = MongoDocument(  host=app.config['mongodb_host'], 
                        port=app.config['mongodb_port'], 
                        user=app.config['mongodb_user'], 
                        pw=app.config['mongodb_pw']
                    )

def get_page(page_id):
    return pages.find_one(page_id)

# Provides a set of macro functions for use within jinja templates
def flask_route_macros():
    MACROS = {}

    MACROS['version'] = __version__
    MACROS['prettify_time_diff'] = prettify_time_diff # convert timestamp to pretty time diff
    # MACROS['quote'] = quote # create a url_safe string
    MACROS['get_page'] = get_page # get a specific page

    return MACROS


# print([x for x in pages.find()])

@app.route('/')
def home():
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))
    return render_template('home.html.jinja', parent_pages=parent_pages, child_pages=child_pages, pages=list(pages.find().sort('position')), **flask_route_macros())

@app.route('/page/<page_id>')
def page(page_id):
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))
    page_data = pages.find_one(page_id)
    page_data['content'] = parse_content_as_markdown(page_data['content'])
    return render_template('page.html.jinja', page=page_data, parent_pages=parent_pages, child_pages=child_pages, pages=list(pages.find().sort('position')), enable_accessibility_audio=config['enable_accessibility_audio'], **flask_route_macros())


@app.route('/create', methods=['GET', 'POST'])
def create():
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        tags = request.form.get('tags').split(',')  # Convert comma-separated tags string to list
        tags = [tag.strip() for tag in tags]  # Strip leading/trailing whitespaces from each tag
        tags = [re.sub(r'\W+', '', tag) for tag in tags] # Strip non alphanumeric chars
        tags = list(set([tag.lower() for tag in tags if len(tag) > 0])) # Remove duplicates and tags with null lengths and cast to lowercase



        parent_id = request.form.get('parent_id')  # Retrieve parent_id from form
        if parent_id == '':
            parent_id = None
        document_id = pages.create({'title': title, 'content': content, 'tags': tags}, parent_id)
        flash("Successfully created page.", 'success')

        if config['enable_accessibility_audio']:
            document_id_str = str(document_id)
            
            # If a process is already running for this document_id, terminate it
            if document_id_str in running_processes:
                os.kill(running_processes[document_id_str], signal.SIGTERM) # terminate the process with the pid

            # Start a new process
            p = Process(target=generate_audio_from_text, args=(document_id, content))
            p.start()
            
            # Store the process pid in the running_processes dict
            running_processes[document_id_str] = p.pid


        return redirect(url_for('home'))

    return render_template('create.html.jinja', pages=list(pages.find().sort('position')), parent_pages=parent_pages, child_pages=child_pages, max_title_length=config['max_title_len'], **flask_route_macros())



@app.route('/edit/<page_id>', methods=['GET', 'POST'])
def edit(page_id):
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        parent_id = request.form.get('parent_id')  # Retrieve parent_id from form
        if parent_id == '':
            parent_id = None

        tags = request.form.get('tags').split(',')  # Convert comma-separated tags string to list
        tags = [tag.strip() for tag in tags]  # Strip leading/trailing whitespaces from each tag
        tags = [re.sub(r'\W+', '', tag) for tag in tags] # Strip non alphanumeric chars
        tags = list(set([tag.lower() for tag in tags if len(tag) > 0])) # Remove duplicates and tags with null lengths and cast to lowercase
 
        document_id = pages.update_one(page_id, {'title': title, 'content': content, 'tags': tags}, parent_id)
        flash("Successfully updated page.", 'success')

        if config['enable_accessibility_audio']:
            document_id_str = str(document_id)
            
            # If a process is already running for this document_id, terminate it
            if document_id_str in running_processes:
                os.kill(running_processes[document_id_str], signal.SIGTERM) # terminate the process with the pid

            # Start a new process
            p = Process(target=generate_audio_from_text, args=(document_id, content))
            p.start()
            
            # Store the process pid in the running_processes dict
            running_processes[document_id_str] = p.pid

        return redirect(url_for('page', page_id=page_id))
    page_data = pages.find_one(page_id)
    return render_template('edit.html.jinja', page=page_data, pages=list(pages.find().sort('position')),  parent_pages=parent_pages, child_pages=child_pages, max_title_length=config['max_title_len'], **flask_route_macros())

@app.route('/tags/<tag_name>', methods=['GET'])
def tags(tag_name):

    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    tagged_pages = list(pages.find({'tags': tag_name}))
    return render_template('tags.html.jinja', tagged_pages=tagged_pages, tag=tag_name, parent_pages=parent_pages, child_pages=child_pages, **flask_route_macros())

@app.route('/bookmark/<page_id>', methods=['GET','POST'])
def toggle_bookmark(page_id, bookmark_page=False):

    bookmark_page = request.args.get('bookmark_page', False)

    # Get the current document
    current_document = pages.find_one(page_id)

    if current_document is None:
        # The page does not exist
        flash(f"This document does not exist.", 'warning')
        return redirect(url_for('home')) # Return to the home view
    else:
        # Toggle the bookmark status
        # print(current_document)
        current_bookmark_status = current_document.get('bookmarked', False)
    
        pages.toggle_bookmark(page_id, not current_bookmark_status)

        if current_bookmark_status:
            flash("Page unbookmarked.", 'success')
        else:
            flash("Page bookmarked.", 'success')

        return redirect(url_for('show_bookmarked')) if bookmark_page else redirect(url_for('page', page_id=page_id))  # Return to the page view


@app.route('/delete/<page_id>', methods=['GET', 'POST'])
def delete(page_id):
    # Check if this page is a parent to any other page
    if pages.is_parent(page_id):
        # This page is a parent, do not delete
        flash("Cannot delete a page with children. Please move or delete the child pages first.", 'warning')
        return redirect(url_for('page', page_id=page_id)) # Return to the page view
    else:
        # No child pages exist, safe to delete
        pages.delete(page_id)
        flash("Successfully deleted page.", 'success')
        return redirect(url_for('home'))



@app.route('/restore/<page_id>', methods=['GET', 'POST'])
def restore(page_id):
    pages.restore(page_id)
    flash("Successfully restored page.", 'success')
    return redirect(url_for('home'))

@app.route('/trash')
def show_trash():
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    trash_pages = pages.find_trash()
    return render_template('trash.html.jinja', trash_pages=trash_pages,  parent_pages=parent_pages, child_pages=child_pages, **flask_route_macros())


@app.route('/bookmarked')
def show_bookmarked():
    
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    # Find all bookmarked pages, sort by last_edited in descending order
    bookmarked_pages = list(pages.find({'bookmarked': True}).sort('last_edited', -1))
    
    return render_template('bookmarked.html.jinja', bookmarked_pages=bookmarked_pages,  parent_pages=parent_pages, child_pages=child_pages, **flask_route_macros())

@app.route('/history/<page_id>', methods=['GET'])
def document_history(page_id):
    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    document_history = list(pages.backups.find({'old_id': ObjectId(page_id)}).sort('last_edited', -1))  
    # print('Last backup:', document_history[0] if document_history else 'No backups')

    current_document = pages.find_one(page_id)
    # print('Current document:', current_document)

    diffs = []
    
    def diff_strings(a, b):
        differ = difflib.Differ()
        diff = differ.compare(a.split(' '), b.split(' '))

        result = ''
        for d in diff:
            if d[0] == ' ':
                result += d[2:] + ' '
            elif d[0] == '-':
                result += f'<span style="background-color: red;">{d[2:]}</span> '
            elif d[0] == '+':
                result += f'<span style="background-color: green;">{d[2:]}</span> '

        return result.strip()

    if document_history:
        current_diff = diff_strings(current_document['content'], document_history[0]['content'])
    else:
        current_diff = ""


    # Add diff between current document and the initial version
    if document_history:
        initial_diff = diff_strings(document_history[-1]['content'], current_document['content'])
        diffs.append(initial_diff)

    for i in range(1, len(document_history)):
        diff = diff_strings(document_history[i-1]['content'], document_history[i]['content'])
        diffs.append(diff)

    return render_template('history.html.jinja', history=document_history, current_diff=current_diff, diffs=diffs, current=current_document, parent_pages=parent_pages, child_pages=child_pages, **flask_route_macros())


@app.route('/restore/<page_id>/<backup_id>', methods=['GET','POST'])
def restore_backup(page_id, backup_id):
    try:
        pages.restore_from_backup(backup_id)
        # return jsonify({"message": f"Restored document {page_id} to version from backup {backup_id}"}), 200
        return redirect(url_for('page', page_id=page_id))
    except ValueError as e:
        return jsonify({"message": str(e)}), 404
    except Exception as e:
        return jsonify({"message": "An error occurred: " + str(e)}), 500


@app.route('/download', methods=['GET', 'POST'])
def download_json():
    
    if request.method == 'POST':
        # get list of document_ids from form
        document_id_list = request.form.getlist('document')

        # fetch documents from db
        documents = []
        for d in document_id_list:
            document = pages.find_one(d)
            document['_id'] = str(document['_id'])
            document['created_at'] = str(document['created_at'])
            document['last_edited'] = str(document['last_edited'])
            documents.append(document)

        with TemporaryDirectory() as tempfile_path:
            file_path = os.path.join(tempfile_path, 'data.json')

            # write the data to a json file
            with open(file_path, 'w') as f:
                json.dump(documents, f)

            # return the json file for download
            return send_file(file_path, as_attachment=True, download_name='data.json')

    parent_pages = list(pages.find({'parent_id': None}).sort('position'))
    child_pages = list(pages.find({'parent_id': {"$ne": None}}))

    # retrieve all documents for display
    docs = list(pages.find())

    # render the template
    return render_template('download.html.jinja', parent_pages=parent_pages, child_pages=child_pages, documents=docs)

#######################
# Internal API Routes
#######################

# render content as markdown
@app.route('/render_md', methods=['POST'])
def render_md():
    content = request.get_json()['content']
    html_content = parse_content_as_markdown(content)
    return jsonify({'content': html_content})


# search query
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')
    if not query:
        return jsonify([])  # Return an empty list if no query is provided

    results = pages.collection.find(
        {"$text": {"$search": query}},
        {"score": {"$meta": "textScore"}}  # Include text search score
    ).sort(
        [("score", {"$meta": "textScore"})]  # Sort by text search score
    ).limit(5)  # Limit results to top 5

    # Convert results to list and convert ObjectIds to strings
    results_list = [
        {
            **result, 
            '_id': str(result['_id'])
        } for result in results
    ]

    return jsonify(results_list)

# get recent activity
@app.route('/recent', methods=['GET'])
def recent():
    # Sort by last edited date in descending order and limit to 5 documents
    recent_docs = list(pages.find().sort('last_edited', -1).limit(5))
    # Convert ObjectIds to strings for JSON serialization
    for doc in recent_docs:
        doc['_id'] = str(doc['_id'])
        doc['created_at'] = prettify_time_diff(doc['created_at'])
        doc['last_edited'] = prettify_time_diff(doc['last_edited'])

    # from pprint import pprint
    # pprint(list(recent_docs))
    return jsonify(recent_docs)

# @app.route('/update_order', methods=['POST'])
# def update_order():
#     new_order = request.get_json()
#     for index, page_id in enumerate(new_order):
#         pages.update_positions(pages.find_one(page_id)['position'], index + 1)
#     return jsonify({"message": "Order updated successfully."}), 200

@app.route('/move', methods=['POST'])
def move():

    data = request.json

    for elem in data:
        try:
            _id = ObjectId(elem['id'])
            new_position = elem['newPosition'] + 1  # Adjust new position index by adding 1
            pages.update_positions(_id, new_position)
        except:
            continue 

    return jsonify({"success": True}), 200



@app.route('/download/<page_id>', methods=['GET'])
def download(page_id):
    # Fetch the document from the database.
    document = pages.find_one(page_id)

    # If the document doesn't exist, return a 404 error.
    if document is None:
        return 'Document not found', 404

    # Create a header from the document title.
    html_content = f'<h1>{document["title"]}</h1>'

    # Convert the markdown content to HTML and add it to the HTML content.
    html_content += parse_content_as_markdown(document['content'])

    # Create a BytesIO object and generate a PDF from the HTML content into it.
    pdf_io = BytesIO()
    pisa.CreatePDF(BytesIO(html_content.encode('utf-8')), pdf_io)

    # Move the cursor of pdf_io to the start of the BytesIO object
    pdf_io.seek(0)

    # Send the BytesIO object as a file download.
    return send_file(pdf_io, mimetype='application/pdf', as_attachment=True, download_name=f'{document["title"]}.pdf')

# return audio for the given file
@app.route('/audio/<document_id>.mp3')
def get_audio(document_id):
    audio_path = f'static/audio/{str(document_id)}.mp3'

    # if not os.path.exists(audio_path):
    #     abort(404)  # Return a 404 error if the file does not exists

    return send_file(audio_path, mimetype='audio/mpeg')
    

#######################
# REST API Routes
#######################

# API documentation
@app.route('/docs/api')
def api_docs():
    return render_template('docs_api.html.jinja', pages=list(pages.find().sort('position')))


@app.route('/api/<page_id>', methods=['GET'])
def api_get(page_id):
    page_data = pages.find_one(ObjectId(page_id))  # Fetch the page from MongoDB
    if page_data:
        page_data['_id'] = str(page_data['_id'])
        return jsonify(page_data), 200
    else:
        return jsonify({"error": "Page not found"}), 404


@app.route('/api/<page_id>', methods=['PUT'])
def api_update(page_id):
    new_data = request.json  # Get the new data from the request
    result = pages.update_one(ObjectId(page_id), new_data)  # Update the page with the new data
    if result.matched_count > 0:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Page not found"}), 404


@app.route('/api/<page_id>', methods=['DELETE'])
def api_delete(page_id):
    pages.delete(ObjectId(page_id))  # Delete the page
    return jsonify({"success": True}), 200


@app.route('/api', methods=['POST'])
def api_create():
    new_data = request.json  # Get the new data from the request
    new_id = pages.create(new_data)  # Create a new page with the new data
    return jsonify({"_id": str(new_id)}), 201


@app.route('/api', methods=['GET'])
def api_get_all():
    all_pages = list(list(pages.find().sort('position')))  # Fetch all pages from MongoDB
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

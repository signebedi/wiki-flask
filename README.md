![logo](static/full_logo.png)

# wiki-flask
a lightweight, programmable wiki API


#### About

The world is becoming an increasingly complex and embedded place. Wiki-Flask is a sleek and customizable wiki API, developed in Flask, providing a streamlined interface for creating and managing graphical content programmatically. It's built atop a RESTful API to facilitate extensibility, automation, and seamless integration into your development ecosystem. 


#### Installation

To install in a development environment, start by downloading the git source.

```
git clone https://github.com/signebedi/wiki-flask.git
```

Next, create the virtual environment.

```
cd flask
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Now, with the virtual environment running, you can run a development server.

```
python app.py
```

Please note, you need to have a MongoDB server running. You can find OS-specific instructions on installing mongodb at https://www.mongodb.com/docs/manual/installation/.
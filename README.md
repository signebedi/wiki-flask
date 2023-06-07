![logo](wikiflask/static/full_logo.png)

# wiki-flask
a lightweight, programmable wiki API


#### About

The world is becoming an increasingly complex and embedded place. Wiki-Flask is a sleek and customizable wiki API, developed in Flask, providing a streamlined interface for creating and managing graphical content programmatically. It's built atop a RESTful API to facilitate extensibility, automation, and seamless integration into your development ecosystem. 


#### Installation

To install in a development environment, start by downloading the git source.

```
git clone https://github.com/signebedi/wiki-flask.git
```

Alternatively, you can install a stable release for a more predictable experience.

```
wget https://github.com/signebedi/wiki-flask/archive/refs/tags/0.2.0.tar.gz
tar -xvf 0.2.0.tar.gz
mv-flask-*/ wiki-flask/
```

Next, create the virtual environment.

```
cd flask-wiki/
python3 -m venv venv
source venv/bin/activate # Windows: venv\Scripts\activate 
pip install -r requirements.txt
```

Now, with the virtual environment running, you can run a development server.

```
flask run
```

You can also install the application using pip after downloading it.

```
pip install -e .
```

And then you can run it with an application-specific command.

```
wikiflask
```

If you would like to run in debug mode, set your flask env.

```
export FLASK_ENV=development # Windows: set FLASK_ENV=development
```

Please note, you need to have a MongoDB server running. You can find OS-specific instructions on installing mongodb at https://www.mongodb.com/docs/manual/installation/.
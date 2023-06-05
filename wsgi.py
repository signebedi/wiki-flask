import os
from wikiflask import app

def main():
    env = os.getenv('FLASK_ENV', 'production')  # If 'FLASK_ENV' isn't set, defaults to 'production'
    debug = env == 'development'
    app.run(debug=debug)

if __name__ == "__main__":
    main()
from setuptools import setup

setup(
    name='wikiflask',
    version='0.2.0',
    author='Sig Janoska-Bedi',
    description=' a lightweight, programmable wiki API',
    url="https://github.com/signebedi/wiki-flask",
    packages=['wikiflask'],
    include_package_data=True,
    install_requires=[
        'Flask==2.3.2',
        'gunicorn==20.1.0',
        'gTTS==2.3.2',
        'Markdown==3.4.3',
        'num2words==0.5.12',
        'pymongo==4.3.3',
        'PyYAML==6.0',
        'xhtml2pdf==0.2.11',
        'pyhanko-certvalidator==0.22.*',
    ],
    entry_points={
        'console_scripts': [
            'wikiflask = wsgi:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        "Framework :: Flask",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ]
)
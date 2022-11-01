[![Unit tests](https://github.com/ccs-amsterdam/amcat4/actions/workflows/unittests.yml/badge.svg)](https://github.com/ccs-amsterdam/amcat4/actions/workflows/unittests.yml)
[![Flake8 & Mypy linting](https://github.com/ccs-amsterdam/amcat4/actions/workflows/linting.yml/badge.svg)](https://github.com/ccs-amsterdam/amcat4/actions/workflows/linting.yml)
[![pip version](https://badge.fury.io/py/amcat4.svg)](https://badge.fury.io/py/amcat4)

# AmCAT4

Server for document management and automatic text analysis, developed as part of [OPTED](https://opted.eu). 
[Learn more](https://opted.eu/fileadmin/user_upload/k_opted/OPTED_deliverable_D7.1.pdf)

See also the [API Documentation](apidoc.md)

## Elasticsearch

AmCAT requires an elasticsearch instance. The easiest way to run one for development is using docker:

```
sudo docker run --name elastic7 -dp 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.17.2
```

## Installing from source

To install AmCAT4 from github and create a virtual environment, run:

```
git clone https://github.com/ccs-amsterdam/amcat4
cd amcat4
python3 -m venv env
env/bin/pip install -e .[dev]
```

Before being able to do anything useful through the API, you will need at least one user which can be created with the command below:

```
env/bin/python amcat4 create-admin --username admin --password supergeheim
```

Now, you can run the backend server:

```
env/bin/python -m amcat4 run
```

This will run the API at (default) locahost port 5000. 
To see documentation, visit http://localhost:5000/docs (Swagger, which comes with interactive "try now" mode) or http://localhost:5000/redoc (redoc, looks somewhat nicer)

Of course, this new instance is still completely empty, so there is little to see. 
If you want to add some test data, you can use the `create-test-data` command, which will upload some State of the Union speeches:

```
env/bin/python -m amcat4 create-test-index
```

(Note: if you get an SSL error, especially on a mac, try running `env/bin/pip install -U certifi`



## Unit tests

To run the unit tests and linting:

```
env/bin/flake8 . --max-line-length=127 --exclude=env
env/bin/pytest
```

Please make sure to run these tests before making any commits!

(obviously, feel free to place your virtual environment in any other location, this is just how I set things up)




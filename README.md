# Payment component

description ...


## Installation

This project is based on the django framework. You need to install the following:
- python 2.7.x
- MySQL server
- Apache web server

First of all, you need to install the MySQL server (see below i.e for ubuntu distribution) and create the database.

```bash
    $ sudo apt-get install mysql-server
    $ sudo apt-get install python-mysqldb
    $ sudo apt-get install libmysqlclient-dev      
    $ sudo mysql_secure_installation   
    $ sudo service mysql restart       
    $ sudo service mysql status
```

```bash
    $ mysql -uroot -p
    > create database `payment` DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_unicode_ci; 
```


Then, you need to install the python and the project dependencies. The python is already installed in Ubuntu 14.04. To check its version, run the command `sudo python -V` from cli. It is common practice to locate the django projects either in `/opt/` or `/var/www/` directories. Create the directory `/opt/prosperity/` using the command `mkdir -p /opt/prosperity/` from cli. Move on this directory and download the project. It should exist the path `/opt/prosperity/Payment` now. 

```bash
    # set 755 permissions on directories
    $ sudo find /opt/prosperity/Payment/ -type d -exec chmod 755 {} \;
    # set 644 permissions on files
    $ sudo find /opt/prosperity/Payment/ -type f -exec chmod 644 {} \;
    $ cd /opt/prosperity/Payment
    # install the python modules (project dependencies)
    $ sudo pip install -r requirements.txt 
    # check the installed python modules
    $ pip freeze
```


You need to update the `/opt/prosperity/Payment/Payment/wsgi.py` file. Append the following statements after the `import os`:

```python
    ...
    import sys
    sys.path.append('/opt/prosperity/Payment')
    sys.path.append('/opt/prosperity/Payment/Payment')
    ...
```

Then, set the host IP of the project in the `/opt/prosperity/Payment/Payment/settings.py` by setting the `HOST_IP` value as a string and the database settings by setting the `DATABASES` dictionary.
> If you have installed the project in localhost and your IP is, let's say, 192.168.1.3, use HOST_IP = "192.168.1.3".

The next commands are used to generate all the required tables in the `payment` database, collect the static files (.js, .css) and alter the user/group permissions on the project.

```bash
    $ cd /opt/prosperity/Payment/
    $ sudo python manage.py makemigrations
    $ sudo python manage.py migrate
    $ sudo python manage.py collectstatic --noinput
    $ sudo chown www-data:www-data -R /opt/prosperity/Payment/
```

For the development phase, it is ok to use the internal Django server. Otherwise, you could configurate the Apache web server.

```bash
    $ cd /opt/prosperity/Payment
    $ sudo python manage.py runsslserver 0.0.0.0:8000
```


## Usage

After the installation, you can run the embed server for development purposes that django framework provides. Therefore, you have to able to access the URL `https://<HOST_IP>:8000/docs` after the execution of the command `python manage.py runsslserver 0.0.0.0:8000`. There, you meet the documentation of the available web services documented via the Swagger (see image in path `/swagger_screenshots/payment_swagger.png`).


## Developers

- Athanasoulis Panagiotis
- Minos Panagiotis 


## Acknowledgements

This project has received funding from the European Union’s Seventh Framework Programme for research, technological development and demonstration under grant agreement no 610510. Visit [http://ds.gpii.net](http://ds.gpii.net/) to find more useful resources.


## License

Apache 2.0



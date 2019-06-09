# EduSchedule
a simple and modern web app that helps students and teachers manage appointments efficiently

available at <https://eduschedule.org>

## Getting Started
Follow these instructions to set up a copy of the project for testing and development.

### Prerequisites
1. If Python is not installed, go ahead and [download and install](https://www.python.org/downloads/) the latest version of Python. This application is written and tested in Python 3.6. Ensure that `pip` and `virtualenv` are working as well; they will be used to install dependencies.
On Ubuntu, install these by running
```shell
sudo apt install python3 python3-pip python3-virtualenv python python-pip python-virtualenv
```
And check if `pip` is working by running
```shell
pip -V
```

2. Install git. It can be installed from the repositories for nearly all Linux distros, but downloads are also available at <https://git-scm.com/downloads>.
On Ubuntu, run
```shell
sudo apt install git
```

### Installing
These instructions assume the use of a Linux system and a bash shell.

1. Clone this repository:
```shell
git clone https://github.com/michaelpolinski/EduSchedule
cd EduSchedule
```

Note: to get up and running quickly, skip steps 2-5 below and simply run
```shell
bash configure.sh
```
Or, to do manual configuration, follow the remaining steps.

2. Create a new virtual environment. This step is optional but highly recommended.
Make a **python3** virtual environment and activate it:
```shell
virtualenv -p python3 venv
source venv/bin/activate
```

3. Install the project's dependencies:
```shell
cd scheduleApp
pip install -r requirements.txt
```
EduSchedule is built using [Django](https://www.djangoproject.com/).

4. Make a copy of the `local_settings.py` file:
```shell
cd scheduleApp
cp local_settings.py.debug.example local_settings.py
```
Now, execute the make_key Python script:
```shell
python make_key.py
```
This will generate a random secret key used by various Django security features and place it into the newly-created `local_settings.py` file; keep this file secret and don't copy it to other machines - especially in production.

5. Run the database migrations:
```shell
cd ..
python manage.py migrate
```

6. Run the server for local testing (runs on localhost:8000):
```shell
python manage.py runserver
```
Ensure that the virtual environment is activated when executing Django manage.py commands.

## Deployment - running on your own server
This section explains how to run EduSchedule on your own server.

### Overview
Running EduSchedule in production requires a publicly-accessible server that has the ability to run Django, has access to a production database, and can send email. It is highly recommended to run EduSchedule on a Linux server or VPS where root shell access (or SSH access) is permitted. The official EduSchedule website is on a VPS running Ubuntu.

A typical configuration would include the following software:
+ NGINX (web server, to handle web traffic from clients and serve static files)
+ Certbot (Let's Encrypt certificate tool, to obtain and deploy HTTPS certificates on the web server)
+ Gunicorn (application server for Django, to run EduSchedule itself)
+ Supervisor (process manager, to restart Gunicorn if it crashes and keep logs)
+ Postfix (mail server, configured to send email from EduSchedule to users)
+ Postgres (database server, to store all the EduSchedule data)
+ EduSchedule and its dependencies (like Django), installed with `pip`

### Software Components - details
Before configuring EduSchedule, the other software must be configured.

**These configuration guides are currently very general and lack precise instructions. Help in expanding them would be greatly appreciated!**

To install all the software components mentioned above, this one-liner will do the job on Ubuntu:
```shell
sudo apt install nginx-full gunicorn supervisor postfix postgresql-contrib certbot python-certbot-nginx
```

##### Configuring NGINX and Certbot (HTTPS certificates)
+ NGINX should be configured to serve HTTP and HTTPS requests on a domain configured for use with the server. Ensure DNS records (specifically A, AAAA, and MX records) point to the server's IP address.
+ Add the domain to the list of `ALLOWED_HOSTS` in `local_settings.py`.
+ Redirect HTTP to HTTPS, and use appropriate security configurations (TLS 1.2 or higher, modern ciphers, and preferably HSTS, which can be preloaded). See the [Mozilla article on server-side TLS](https://wiki.mozilla.org/Security/Server_Side_TLS) and the [Mozilla SSL Configuration Generator](https://mozilla.github.io/server-side-tls/ssl-config-generator/), which can help a lot with the security aspect of setting up NGINX. 
+ Obtain HTTPS certificates for your domain using Certbot (use `certbot certonly`), and add them to the NGINX configuration accordingly. Installing the NGINX plugin for Certbot is preferred, as the certificates can then be renewed without needing to restart NGINX.
+ Configure NGINX to serve static files on `https://[example.com]/static/` and pass other requests to Gunicorn, the application server that runs Django. The static files directory is, by default, in `EduSchedule/scheduleApp/scheduleApp/staticfiles/` (this can be changed in `local_settings.py`).

##### Configuring Gunicorn
+ Create a bash script that will start Gunicorn. This script should activate the `virtualenv` (see Getting Started above), set the environment variables DJANGO\_SETTINGS\_MODULE and PYTHONPATH, and start `gunicorn`. Don't forget to make it executable with `chmod +x`.
+ See the Gunicorn [deployment docs](https://docs.gunicorn.org/en/latest/deploy.html) for instructions and for help on configuring Gunicorn to work with NGINX.

##### Configuring Supervisor
+ Create a Supervisor configuration file in `/etc/supervisor/conf.d/` with `autostart=true` that will run the bash script that was created to start Gunicorn.

##### Configuring Postgres (database server)
+ Create a new database user and a new database, giving the user a strong password.
+ Copy the database name, username, and password to the `local_settings.py` file in the appropriate place so that Django can communicate with the database.
+ Be sure to restrict access to the database using a firewall like `ufw` (comes with Ubuntu) to prevent breaches.

##### Configuring Postfix (email server)
+ Configure Postfix as a send-only mail server. The same certificates used for encrypting HTTPS traffic should be used for Postfix to encrypt emails going to users.
+ The Postfix documentation can be cryptic. [This article](https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-postfix-as-a-send-only-smtp-server-on-ubuntu-16-04) is a very helpful resource for configuring your email server.
+ Be sure to restrict access to email server using a firewall like `ufw` (comes with Ubuntu) to prevent abuse of the mail server.
+ Configure the DEFAULT\_FROM\_EMAIL in `local_settings.py` so that emails sent to users come from a reasonable address, like no-reply@example.com.


##### Configuring EduSchedule
+ Follow the "Getting Started" instructions above. Instead of using `local_settings.py.debug.example` as a template, use `local_settings.py.example` and configure it to integrate with the rest of the software now running on your production server.
+ Instead of running the server with `python manage.py runserver`, use `supervisorctl` to start and stop the server.  
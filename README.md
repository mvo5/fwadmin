Fwadmin
=======
[![Build Status](https://travis-ci.org/ZIMK/fwadmin.png)](https://travis-ci.org/ZIMK/fwadmin)
[![Coverage Status](https://coveralls.io/repos/ZIMK/fwadmin/badge.png?branch=master)](https://coveralls.io/r/ZIMK/fwadmin)

Django based self-serivce firwall config tool.

The use-case is that a group of trusted users can easily configure
simple fireall rules for a set of machines. Each machine has a owner
and the rules are valid for a certain amount of time only, then they
need to be refreshed.

Supported firewalls are: cisco, ubuntu ufw

Dependencies to run in production:
 - python-django (tested with 1.4 and 1.5)
 - python-django-auth-ldap
 - python-netaddr
 - python-django-sekizai
 - [bower](https://github.com/twitter/bower)

Dependencies for testing/development:
 - python-mock

How to install javascript dependencies:
```
$ bower install
```

How to run the testsuite:
```
$ python manage.py test fwadmin
```

One time setup:
```
$ echo "my-secret-ldap-password" > django_project/ldap-password
$ python django_project/first_time_init.py
$ python manage.py syncdb
```

How to test interactively:
```
$ python manage.py runserver
```

go to the admin interface:
 [http://localhost:8000/admin/]()
and create user(s) and add them to
the "Mitarb".

If you want users to have moderation capabilities
add them to "G-zentrale-systeme".

Then go to:
 [http://localhost:8000/fwadmin/]()
and create hosts/rules.

To generate rules run:
```
$ python manange runrules ufw
```
(supported are currently cisco, ufw)

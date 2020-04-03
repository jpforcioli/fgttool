Introduction
============

Use this Python script from the command-line to get started with the
FortiOS REST API for some simple object management.

This tool allows you to create, delete, edit or retrieve objects via
the REST API and presents the result in the native JSON format as
output on the console.

The tool also allows you to copy objects/tables from one VDOM to
another via the ``copy`` option. 

System Requirements
===================

- Linux or Windows (with Python)
- FortiOS 5.4+
- Python 2 or 3
- Pip

Installation
============

1. Download ``fgttool.py``
2. Make sure python module requests is installed

   .. code-block:: shell

		   $ pip list | grep requests
		   requests   2.23.0

   If not installed:

      .. code-block:: shell

		      $ pip install requests

Usage
=====

This version supports some basic commands as following:

.. code-block:: shell

		./fgttool.py --help
		usage: fgttool.py [-h] [--ip IP] [--login LOGIN] [--password PASSWORD] [-v] [-d] [--version] {get,delete,create,edit,copy} ...

		Python tool to interact with FGT via rest api

		optional arguments:
		  -h, --help            show this help message and exit
		  --ip IP, -i IP        fortigate IP
		  --login LOGIN, -l LOGIN
                                        fortigate login
		  --password PASSWORD, -p PASSWORD
                                        fortigate password
		  -v, --verbose         increase output verbosity
		  -d, --dryrun          dryrun the command without committing any changes
		  --version             show version number and exit

		commands:
		  {get,delete,create,edit,copy}
		    get                 get object or table
		    delete              delete object or table
		    create              create object
		    edit                edit object
		    copy                copy object or table from one vdom to another including referenced objects

What's New
==========

- 0.3.2

  - New command line options: ``--ip``, ``--login`` and ``--password``
    to enter the FortiGate IP address, the administrator's credentials
    respectively

    **Notes**

       - You can still open the ``fgttool.py`` file and edit the
	 variables ``fgt_ip``, ``fgt_login``, ``fgt_password``. 

       - If you want to be prompted to enter a password, set variable
	 ``fgt_password`` to ``None``.

       - In any cases, the values provided at command line will
	 prevail.

Examples
========

- To get list of firewall addresses from VDOM ``root``

  .. code-block:: shell

		  $ ./fgttool.py get firewall/address --vdom root
		  
  By default ``fgttool.py`` will consider VDOM ``root``; so you can
  omit the ``--vdom root`` arguments. 

  This command will produce same output  as previous one: 

  .. code-block:: shell

		  $ ./fgttool.py get firewall/address

- To get a specific firewall address

  To get the firewall address ``all``:

  .. code-block:: shell

		  $ ./fgttool.py get firewall/address/all

- To get the list of VDOMs

  .. code-block:: shell

		  $ ./fgttool.py get system/vdom

- To get a specific firewall address group

  .. code-block:: shell

		  $ ./fgttool.py get firewall/addrgrp/GRP_001

- To get members of a firewall address group

  To get the members of the firewall address group ``GRP_001``:

  .. code-block:: shell

		  $ ./fgttool.py get firewall/addrgrp/GRP_001/member


- To add a new member in a firewall address group

  To add firewall address ``HOST_005`` as a new member of firewall
  address group ``GRP_001``: 

  .. code-block:: shell

		  $ ./fgttool.py create firewall/addrgrp/GRP_001/member --data '{"name": "HOST_005"}'

  **Notes**

   - Object ``HOST_001`` has to exist.
   - Existing members will be preserved, object ``HOST_005`` is just
     added to the current members list. 
   - The argument of the ``--data`` command line argument must be JSON
     formatted. 
	  
- To delete an existing member from a firewall address group

  To delete firewall address ``HOST_005`` from firewall address group
  ``GRP_001``:

  .. code-block:: shell

		  $ ./fgttool.py delete firewall/addrgrp/GRP_001/member/HOST_005

- To get list of firewall services

  .. code-block:: shell

		  $ ./fgttool.py get firewall.service/custom

  **Note**

    - Note the usage of the ``.`` when the table we want to reach
      *here ``custom``) is deeper than two levels.

- To update an existing firewall service

  To change the port number and the comment of an existing service:

  .. code-block:: shell

		  $ ./fgttool.py edit firewall.service/custom/tcp_11112 --data '{"tcp-portrante": 8888, "comment": "something"}'

- To rename an existing firewall service

  .. code-block:: shell

		  $ ./fgttool.py edit firewall.service/custom/tcp_11112 --data '{"name": "tcp_8888"}'
		  
- To copy an object/table between vdoms

  To copy firewall address group ``GRP_001`` (and recursively all its
  referenced members, including sub groups) from vdom ``vdom1`` to 
  vdom ``vdom2``:

  .. code-block:: shell

		  $ ./fgttool.py copy firewall/addrgrp/GRP_001 vdom1 vdom2

- To copy all firewall vips from vdom1 to vdom2

  .. code-block:: shell

		  $ ./fgttool.py copy firewall/vip vdom1 vdom2  

# coding: utf-8

import requests
import argparse
import sys
import json
import getpass
from pprint import pprint

import logging

logging.captureWarnings(True)

__version__ = "0.3.3"


class FGT(object):
    """
    Base class to send GET/POST/PUT/DELETE request to FGT
      . All requests are from the same session initiated by each login
    """

    def __init__(self):
        pass

    def update_csrf(self):
        # retrieve server csrf and update session's headers
        for cookie in self.session.cookies:
            if cookie.name == "ccsrftoken":
                csrftoken = cookie.value[1:-1]  # token stored as a list
                self.session.headers.update({"X-CSRFTOKEN": csrftoken})

    def login(self, ip, login, password, csrf=True, port=443):
        # close existing session if any
        self.logout()

        self.ip = ip
        self.login = login

        self.url_prefix = "https://" + self.ip + ":" + str(port)

        # start fresh new session
        self.session = requests.session()
        url = self.url_prefix + "/logincheck"
        try:
            res = self.session.post(
                url, data="username=" + login + "&secretkey=" + password, verify=False
            )
        except requests.exceptions.RequestException as e:
            print(e)
            print("LOGIN failed")
            exit()

        if res.text.find("error") != -1:
            # found some error in the response, consider login failed
            print("LOGIN failed")
            return False

        if res.text.find("license") != -1:
            # found some licensing issue in the response, consider login failed
            print("LOGIN failed: FortiGate-VM license has probably expired")
            return False

        # update session's csrftoken
        if csrf:
            self.update_csrf()

        return True

    def logout(self):
        if hasattr(self, "session"):
            url = self.url_prefix + "/logout"
            self.session.post(url)

    def get(self, url, **options):
        url = self.url_prefix + url
        try:
            res = self.session.get(url, params=options.get("params"))
        except requests.exceptions.RequestException as e:
            print(e)
            exit()
        return res

    def post(self, url, override=None, **options):
        url = self.url_prefix + url
        data = options.get("data") if options.get("data") else None

        # override session's HTTP method if needed
        if override:
            self.session.headers.update({"X-HTTP-Method-Override": override})
        try:
            res = self.session.post(
                url,
                params=options.get("params"),
                data=json.dumps(data),
                files=options.get("files"),
            )
        except requests.exceptions.RequestException as e:
            print(e)
            exit()

        # restore original session
        if override:
            del self.session.headers["X-HTTP-Method-Override"]
        return res

    def put(self, url, **options):
        url = self.url_prefix + url
        data = options.get("data") if options.get("data") else None
        try:
            res = self.session.put(
                url,
                params=options.get("params"),
                data=json.dumps(data),
                files=options.get("files"),
            )
        except requests.exceptions.RequestException as e:
            print(e)
            exit()
        return res

    def delete(self, url, **options):
        url = self.url_prefix + url
        try:
            res = self.session.delete(url, params=options.get("params"))
        except requests.exceptions.RequestException as e:
            print(e)
            exit()
        return res

    # function to retrieve the mkey name
    def get_mkey_name(self, resource, vdom):
        url_string = "/api/v2/cmdb/{}".format(resource)
        res = self.get(url=url_string, params={"vdom": vdom, "action": "schema"})
        rjson = get_json(res)

        return rjson.get("results").get("mkey")

    def resource_exists(self, resource, vdom):
        url_string = "/api/v2/cmdb/{}".format(resource)
        res = self.get(url=url_string, params={"vdom": vdom})
        rjson = get_json(res)

        if rjson.get("results"):
            return True

        return False

    # function to retrieve resource
    def get_command(self, args):
        resource = normalize_resource(args.resource)
        print("Get [{}] (vdom: {})".format(resource, args.vdom))

        # only send request if not dryrun
        if not args.dryrun:
            # retrieve resource
            url_string = "/api/v2/cmdb/{}".format(resource)
            res = self.get(url=url_string, params={"vdom": args.vdom})
            check_response(res, True)  # always print JSON response for get

    # function to delete resource
    def delete_command(self, args):
        resource = normalize_resource(args.resource)
        print("Delete [{}] (vdom: {})".format(resource, args.vdom))

        # only send request if not dryrun
        if not args.dryrun:
            # delete resource
            url_string = "/api/v2/cmdb/{}".format(resource)
            res = self.delete(url=url_string, params={"vdom": args.vdom})
            check_response(res, args.verbose)

    # function to create resource
    def create_command(self, args):
        resource = normalize_resource(args.resource)
        print("Add [{}] in [{}] (vdom: {})".format(args.data, resource, args.vdom))

        # only send request if not dryrun
        if not args.dryrun:
            # create resource
            url = "/api/v2/cmdb/{}".format(resource)
            res = self.post(url=url, params={"vdom": args.vdom}, data=args.data)
            check_response(res, args.verbose)

    # function to edit resource
    def edit_command(self, args):
        resource = normalize_resource(args.resource)
        print("Update [{}] with [{}] (vdom: {})".format(resource, args.data, args.vdom))
        # only send request if not dryrun
        if not args.dryrun:
            # edit resource
            res = self.put(
                url="/api/v2/cmdb/{}".format(resource),
                params={"vdom": args.vdom},
                data=args.data,
            )
            check_response(res, args.verbose)

    # function to copy resource (recursive)
    def copy_command(self, args, space=""):
        # Very ugly...
        # Should be reworked completely
        table = False
        padding = ""
        resource = normalize_resource(args.resource)

        if len(resource.split("/")) == 2:
            print(
                "Copy table [{}] from vdom[{}] to vdom[{}]".format(
                    resource, args.oldvdom, args.newvdom
                )
            )
            table = True

        # retrieve resource in old vdom
        res = self.get(
            url="/api/v2/cmdb/{}".format(resource),
            params={
                "vdom": args.oldvdom,
                "skip": 1,  # skip inapplicable fields
                "datasource": 1,
            },
        )  # need datasource for deep copy
        rjson = get_json(res)
        if args.verbose:
            pprint(rjson)

        # skip if cannot get json result
        if not rjson or "results" not in rjson:
            print(
                "{}Error: fail to retrieve resource {} in vdom[{}]".format(
                    space, args.resource, args.oldvdom
                )
            )
            return

        # retrieve the master key for resource in oldvdom
        mkey_name = self.get_mkey_name(resource, args.oldvdom)

        # copy all objects in table
        for data in rjson["results"]:
            # copy all object attributes
            for key, value in data.items():
                # recursively copy all non-empty referenced objects
                if value and type(value) is list:
                    # copy all referenced objects
                    for item in value:
                        # only copy object that has valid datasource
                        if "datasource" in item:
                            child_path = item["datasource"].replace(".", "/")
                            # handle special case like firewall.service/custom
                            if len(child_path.split("/")) > 2:
                                child_path = child_path.replace("/", ".", 1)
                            child_mkey_name = self.get_mkey_name(
                                child_path, args.oldvdom
                            )
                            child_resource = child_path + "/" + item[child_mkey_name]
                            args.resource = child_resource
                            new_space = space + "  "
                            self.copy_command(args, space=new_space)

            if table:
                mkey = data[mkey_name]
                new_resource = "{}/{}".format(resource, mkey)
                padding = space + "  "
            else:
                new_resource = resource

            # test if object exist in destination vdom
            if self.resource_exists(new_resource, args.newvdom):
                print(
                    "{}Skipped: resource [{}] already exists in vdom[{}]".format(
                        padding, new_resource, args.newvdom
                    )
                )
                continue

            # only send request if not dryrun
            if not args.dryrun:
                # Remove mkey from the resource
                print(
                    "{}Copy [{}] from vdom[{}] to vdom[{}]".format(
                        padding, new_resource, args.oldvdom, args.newvdom
                    )
                )
                new_resource = "/".join(new_resource.split("/")[0:-1])
                # create resource in another vdom
                res = self.post(
                    url="/api/v2/cmdb/{}".format(new_resource),
                    params={"vdom": args.newvdom},
                    data=(data),
                )
                check_response(res, args.verbose)


# function to process command arguments
def process_commands(ip, port, login, password):

    # Declare the FortiGate instance
    fgt = FGT()

    # inititate command parsers
    tool = argparse.ArgumentParser(
        description="Python tool to interact with FGT via rest api"
    )
    commands = tool.add_subparsers(title="commands", dest="COMMANDS")

    # common arguments
    tool.add_argument("--ip", "-i", nargs="?", default=ip, help="FortiGate IP")
    tool.add_argument("--port", nargs="?", default=port, help="FortiGate port")
    tool.add_argument("--login", "-l", nargs="?", default=login, help="FortiGate login")
    tool.add_argument(
        "--password",
        "-p",
        nargs="?",
        const=None,
        default=password,
        help="FortiGate password",
    )
    tool.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    tool.add_argument(
        "-d",
        "--dryrun",
        help="dryrun the command without committing any changes",
        action="store_true",
    )
    tool.add_argument(
        "--version",
        help="show version number and exit",
        action="version",
        version="%(prog)s {}".format(__version__),
    )

    # get command (get firewall.address.test --vdom root)
    command_get = commands.add_parser("get", help="get object or table")
    command_get.add_argument(
        "resource",
        help="full path to the object or table, ie. firewall/address or firewall/address/test or firewall.service/custom/test",
    )
    command_get.add_argument(
        "-V", "--vdom", default="root", help="vdom of the resource, default is root"
    )
    command_get.set_defaults(func=fgt.get_command)

    # delete command (delete firewall.address.test --vdom root)
    command_delete = commands.add_parser("delete", help="delete object or table")
    command_delete.add_argument(
        "resource",
        help="full path to the object or table, ie. firewall/address or firewall/address/test or firewall.service/custom/test",
    )
    command_delete.add_argument(
        "-V", "--vdom", default="root", help="vdom of the resource, default is root"
    )
    command_delete.set_defaults(func=fgt.delete_command)

    # create command (create firewall.address.test {"comment":"test"} --vdom root)
    command_create = commands.add_parser("create", help="create object")
    command_create.add_argument(
        "resource",
        help="full path to the object or table, ie. firewall/address or firewall/address/test or firewall.service/custom/test",
    )
    command_create.add_argument(
        "-D",
        "--data",
        type=json.loads,
        default=None,
        help='object data in JSON format \'{"comment":"test"}\'',
    )
    command_create.add_argument(
        "-V", "--vdom", default="root", help="vdom of the resource, default is root"
    )
    command_create.set_defaults(func=fgt.create_command)

    # edit command (create firewall.address.test {"comment":"test"} --vdom root)
    command_edit = commands.add_parser("edit", help="edit object")
    command_edit.add_argument(
        "resource",
        help="full path to the object or table, ie. firewall/address or firewall/address/test or firewall.service/custom/test",
    )
    command_edit.add_argument(
        "-D",
        "--data",
        type=json.loads,
        default=None,
        help='object data in string format \'{"comment":"test"}\'',
    )
    command_edit.add_argument(
        "-V", "--vdom", default="root", help="vdom of the resource, default is root"
    )
    command_edit.set_defaults(func=fgt.edit_command)

    # copy command
    command_copy = commands.add_parser(
        "copy",
        help="copy object or table from one vdom to another including referenced objects",
    )
    command_copy.add_argument(
        "resource",
        help="full path to the object or table, ie. firewall/address or firewall/address/test or firewall.service/custom/test",
    )
    command_copy.add_argument("oldvdom", help="vdom of the original resource, ie. root")
    command_copy.add_argument("newvdom", help="vdom of the new resource, ie. vdom1")
    command_copy.set_defaults(func=fgt.copy_command)

    # import command (import firewall.address.test --vdom root --file path/to/file)
    # export command (export firewall.address.test --vdom root --file path/to/file)

    # process commands
    args = tool.parse_args()

    if args.ip:
        ip = args.ip
    if args.login:
        login = args.login
    if args.port:
        port = args.port

    if args.password or args.password == "":
        password = args.password
    else:
        password = getpass.getpass()

    if fgt.login(ip, login, password, port=port):
        if hasattr(args, "func"):
            args.func(args)

        fgt.logout()


# function to parse resource path, name and mkey
def parse_resource(resource):
    obj_list = resource.split("/")
    mkey = None
    member = None
    child = None
    if len(obj_list) == 2:
        path = obj_list[0]
        name = obj_list[1]
    elif len(obj_list) == 3:
        path = obj_list[0]
        name = obj_list[1]
        mkey = obj_list[2]
    elif len(obj_list) == 4:
        path = obj_list[0]
        name = obj_list[1]
        mkey = obj_list[2]
        member = obj_list[3]
    elif len(obj_list) == 5:
        path = obj_list[0]
        name = obj_list[1]
        mkey = obj_list[2]
        member = obj_list[3]
        child = obj_list[4]
    else:
        print("Invalid resource", resource, "please use / to separate path/name/mkey")
        exit()
    return (path, name, mkey, member, child)


# function to retrieve json data from HTTP response (return False if fails)
def get_json(response):
    try:
        rjson = response.json()
    except UnicodeDecodeError as e:
        print("Cannot decode json data in HTTP response")
        return False
    except:
        e = sys.exc_info()[0]
        print(e)
        return False
    else:
        return rjson


# Function to normalize the resource
def normalize_resource(resource):
    # for the moment, we just strip {trail,lead}ing '/'.
    return resource.strip("/")


# function to check response
def check_response(res, verbose):
    print(res)
    rjson = get_json(res)
    if verbose:
        pprint(rjson)
    if not rjson:
        print("fail to retrieve JSON response")
    else:
        status = rjson["http_status"]
        if status == 200:
            if verbose:
                print("200 successful request")
        elif status == 400:
            print("400 Invalid request format")
        elif status == 403:
            print("403 Permission denied")
        elif status == 404:
            print("404 None existing resource")
        elif status == 405:
            print("405 Unsupported method")
        elif status == 424:
            print("424 Dependency error")
        elif status == 500:
            print("500 Internal server error")
        else:
            print(status, "Unknown error")


###############################################################################
if __name__ == "__main__":
    # You can use command line arguments to override following variables.

    # FortiGate IP
    fgt_ip = "10.210.35.101"

    # FortiGate port
    fgt_port = "443"

    # FortiGate login
    fgt_login = "admin"

    # FortiGate password.
    # Use None if you want to get prompted
    fgt_password = "fortinet"

    process_commands(fgt_ip, fgt_port, fgt_login, fgt_password)

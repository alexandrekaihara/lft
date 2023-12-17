"""
Node objects for Mininet.

Nodes provide a simple abstraction for interacting with hosts, switches
and controllers. Local nodes are simply one or more processes on the local
machine.

Node: superclass for all (primarily local) network nodes.

Host: a virtual host. By default, a host is simply a shell; commands
    may be sent using Cmd (which waits for output), or using sendCmd(),
    which returns immediately, allowing subsequent monitoring using
    monitor(). Examples of how to run experiments using this
    functionality are provided in the examples/ directory. By default,
    hosts share the root file system, but they may also specify private
    directories.

CPULimitedHost: a virtual host whose CPU bandwidth is limited by
    RT or CFS bandwidth limiting.

Switch: superclass for switch nodes.

UserSwitch: a switch using the user-space switch from the OpenFlow
    reference implementation.

OVSSwitch: a switch using the Open vSwitch OpenFlow-compatible switch
    implementation (openvswitch.org).

Controller: superclass for OpenFlow controllers. The default controller
    is controller(8) from the reference implementation.

RemoteController: a remote controller node, which may use any
    arbitrary OpenFlow-compatible controller, and which is not
    created or managed by Mininet.

Future enhancements:

- Possibly make Node, Switch and Controller more abstract so that
  they can be used for both local and remote nodes

- Create proxy objects for remote nodes (Mininet: Cluster Edition)
"""
import errno
import os
import re
import pty
import select
import docker
import json
from subprocess import check_output
from time import sleep
from re import findall

from mininet.node import Node, Host
from mininet.moduledeps import moduleDeps, pathCheck, TUN
from mininet.util import ( quietRun, errRun, which)
from mininet.log import info, error, warn, debug
from mn_wifi.node import Station
from containernet.link import Intf, TCIntf, OVSIntf
from distutils.version import StrictVersion


class Docker ( Host ):
    """Node that represents a docker container.
    This part is inspired by:
    http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/
    We use the docker-py client library to control docker.
    """

    def __init__(self, name, dimage=None, dcmd=None, did=None, **kwargs):
        """
        Creates a Docker container as Mininet host.

        Resource limitations based on CFS scheduler:
        * cpu.cfs_quota_us: the total available run-time within a period (in microseconds)
        * cpu.cfs_period_us: the length of a period (in microseconds)
        (https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt)

        Default Docker resource limitations:
        * cpu_shares: Relative amount of max. avail CPU for container
            (not a hard limit, e.g. if only one container is busy and the rest idle)
            e.g. usage: d1=4 d2=6 <=> 40% 60% CPU
        * cpuset_cpus: Bind containers to CPU 0 = cpu_1 ... n-1 = cpu_n (string: '0,2')
        * mem_limit: Memory limit (format: <number>[<unit>], where unit = b, k, m or g)
        * memswap_limit: Total limit = memory + swap

        All resource limits can be updated at runtime! Use:
        * updateCpuLimits(...)
        * updateMemoryLimits(...)
        """
        self.dimage = dimage
        self.dnameprefix = "mn"
        self.dcmd = dcmd if dcmd is not None else "/bin/bash"
        self.dc = None  # pointer to the dict containing 'Id' and 'Warnings' keys of the container
        self.dcinfo = None
        self.func = []
        self.did = did  # Id of running container
        #  let's store our resource limits to have them available through the
        #  Mininet API later on
        defaults = { 'cpu_quota': -1,
                     'cpu_period': None,
                     'cpu_shares': None,
                     'cpuset_cpus': None,
                     'mem_limit': None,
                     'memswap_limit': None,
                     'environment': {},
                     'volumes': [],  # use ["/home/user1/:/mnt/vol2:rw"]
                     'tmpfs': [],  # use ["/home/vol1/:size=3G,uid=1000"]
                     'network_mode': None,
                     'privileged': False,
                     'publish_all_ports': True,
                     'port_bindings': {},
                     'ports': [],
                     'dns': [],
                     'ipc_mode': None,
                     'devices': [],
                     'cap_add': ['net_admin'],  # we need this to allow mininet network setup
                     #'storage_opt': None,
                     'sysctls': {}
                     }
        defaults.update( kwargs )

        if 'net_admin' not in defaults['cap_add']:
            defaults['cap_add'] += ['net_admin']  # adding net_admin if it's cleared out to allow mininet network setup

        # keep resource in a dict for easy update during container lifetime
        self.resources = dict(
            cpu_quota=defaults['cpu_quota'],
            cpu_period=defaults['cpu_period'],
            cpu_shares=defaults['cpu_shares'],
            cpuset_cpus=defaults['cpuset_cpus'],
            mem_limit=defaults['mem_limit'],
            memswap_limit=defaults['memswap_limit']
        )

        self.volumes = defaults['volumes']
        self.tmpfs = defaults['tmpfs']
        self.environment = {} if defaults['environment'] is None else defaults['environment']
        # setting PS1 at "docker run" may break the python docker api (update_container hangs...)
        # self.environment.update({"PS1": chr(127)})  # CLI support
        self.network_mode = defaults['network_mode']
        self.privileged = defaults['privileged']
        self.publish_all_ports = defaults['publish_all_ports']
        self.port_bindings = defaults['port_bindings']
        self.dns = defaults['dns']
        self.ipc_mode = defaults['ipc_mode']
        self.devices = defaults['devices']
        self.cap_add = defaults['cap_add']
        self.sysctls = defaults['sysctls']
        #self.storage_opt = defaults['storage_opt']

        # setup docker client
        # self.dcli = docker.APIClient(base_url='unix://var/run/docker.sock')
        self.dcli = docker.from_env().api

        # pull image if it does not exist
        if self.dimage:
            self._check_image_exists(dimage, True)

        # for DEBUG
        debug("Created docker container object %s\n" % name)
        debug("image: %s\n" % str(self.dimage))
        debug("dcmd: %s\n" % str(self.dcmd))
        info("%s: kwargs %s\n" % (name, str(kwargs)))

        # creats host config for container
        # see: https://docker-py.readthedocs.org/en/latest/hostconfig/
        hc = self.dcli.create_host_config(
            network_mode=self.network_mode,
            privileged=self.privileged,
            binds=self.volumes,
            tmpfs=self.tmpfs,
            publish_all_ports=self.publish_all_ports,
            port_bindings=self.port_bindings,
            mem_limit=self.resources.get('mem_limit'),
            cpuset_cpus=self.resources.get('cpuset_cpus'),
            dns=self.dns,
            ipc_mode=self.ipc_mode,  # string
            devices=self.devices,  # see docker-py docu
            cap_add=self.cap_add,  # see docker-py docu
            sysctls=self.sysctls,  # see docker-py docu
            #storage_opt=self.storage_opt
        )

        if kwargs.get("rm", False):
            container_list = self.dcli.containers(all=True)
            for container in container_list:
                for container_name in container.get("Names", []):
                    if "%s.%s" % (self.dnameprefix, name) in container_name:
                        self.dcli.remove_container(container="%s.%s" % (self.dnameprefix, name), force=True)
                        break

        if self.did:
            self.dc = {'Id': '{}'.format(self.did), 'Warnings': []}
            self.existing_container = 1
        else:
            # create new docker container
            self.dc = self.dcli.create_container(
                name="%s.%s" % (self.dnameprefix, name),
                image=self.dimage,
                command=self.dcmd,
                entrypoint=list(),  # overwrite (will be executed manually at the end)
                stdin_open=True,  # keep container open
                tty=True,  # allocate pseudo tty
                environment=self.environment,
                #network_disabled=True,  # docker stats breaks if we disable the default network
                host_config=hc,
                ports=defaults['ports'],
                labels=['com.containernet'],
                volumes=[self._get_volume_mount_name(v) for v in self.volumes if self._get_volume_mount_name(v) is not None],
                hostname=name
            )

        # start the container
        self.dcli.start(self.dc)
        debug("Docker container %s started\n" % name)

        # fetch information about new container
        self.dcinfo = self.dcli.inspect_container(self.dc)
        self.did = self.dcinfo.get("Id")

        # call original Node.__init__
        Node.__init__(self, name, **kwargs)

        # let's initially set our resource limits
        self.update_resources(**self.resources)

    def start(self):
        # Containernet ignores the CMD field of the Dockerfile.
        # Lets try to load it here and manually execute it once the
        # container is started and configured by Containernet:
        cmd_field = self.get_cmd_field(self.dimage)
        entryp_field = self.get_entrypoint_field(self.dimage)
        if entryp_field is not None:
            if cmd_field is None:
                cmd_field = list()
            # clean up cmd_field
            try:
                cmd_field.remove(u'/bin/sh')
                cmd_field.remove(u'-c')
            except ValueError:
                pass
            # we just add the entryp. commands to the beginning:
            cmd_field = entryp_field + cmd_field
        if cmd_field is not None:
            cmd_field.append("> /dev/pts/0 2>&1")  # make output available to docker logs
            cmd_field.append("&")  # put to background (works, but not nice)
            info("{}: running CMD: {}\n".format(self.name, cmd_field))
            self.cmd(" ".join(cmd_field))

    def get_cmd_field(self, imagename):
        """
        Try to find the original CMD command of the Dockerfile
        by inspecting the Docker image.
        Returns list from CMD field if it is different from
        a single /bin/bash command which Containernet executes
        anyhow.
        """
        try:
            imgd = self.dcli.inspect_image(imagename)
            cmd = imgd.get("Config", {}).get("Cmd")
            assert isinstance(cmd, list)
            # filter the default case: a single "/bin/bash"
            if "/bin/bash" in cmd and len(cmd) == 1:
                return None
            return cmd
        except BaseException as ex:
            error("Error during image inspection of {}:{}"
                  .format(imagename, ex))
        return None

    def get_entrypoint_field(self, imagename):
        """
        Try to find the original ENTRYPOINT command of the Dockerfile
        by inspecting the Docker image.
        Returns list or None.
        """
        try:
            imgd = self.dcli.inspect_image(imagename)
            ep = imgd.get("Config", {}).get("Entrypoint")
            if isinstance(ep, list) and len(ep) < 1:
                return None
            return ep
        except BaseException as ex:
            error("Error during image inspection of {}:{}"
                  .format(imagename, ex))
        return None

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
        # mnexec: (c)lose descriptors, (d)etach from tty,
        # (p)rint pid, and run in (n)amespace
        # opts = '-cd' if mnopts is None else mnopts
        # if self.inNamespace:
        #     opts += 'n'
        # bash -i: force interactive
        # -s: pass $* to shell, and make process easy to find in ps
        # prompt is set to sentinel chr( 127 )
        if hasattr(self, 'existing_container'):
            cmd = ['docker', 'exec', '-it', '%s' % self.did, 'env', 'PS1=' + chr(127),
                   'bash', '--norc', '-is', 'mininet:' + self.name]
        else:
            cmd = ['docker', 'exec', '-it', '%s.%s' % (self.dnameprefix, self.name), 'env', 'PS1=' + chr(127),
                   'bash', '--norc', '-is', 'mininet:' + self.name]
        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        self.master, self.slave = pty.openpty()
        self.shell = self._popen( cmd, stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                  close_fds=False )
        self.stdin = os.fdopen( self.master, 'r' )
        self.stdout = self.stdin
        self.pid = self._get_pid()
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

    def _get_volume_mount_name(self, volume_str):
        """ Helper to extract mount names from volume specification strings """
        parts = volume_str.split(":")
        if len(parts) < 3:
            return None
        return parts[1]

    def terminate( self ):
        """ Stop docker container """
        if not self._is_container_running():
            return
        try:
            if not hasattr(self, 'existing_container'):
                self.dcli.remove_container(self.dc, force=True, v=True)
        except docker.errors.APIError:
            warn("Warning: API error during container removal.\n")

        self.cleanup()

    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete."""
        self._check_shell()
        if not self.shell:
            return
        Host.sendCmd( self, *args, **kwargs )

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in node's namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        if not self._is_container_running():
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            return
        mncmd = ["docker", "exec", "-t", "%s.%s" % (self.dnameprefix, self.name)]
        return Node.popen( self, *args, mncmd=mncmd, **kwargs )

    def cmd(self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )
        self.sendCmd( *args, **kwargs )
        return self.waitOutput( verbose )

    def _get_pid(self):
        state = self.dcinfo.get("State", None)
        if state:
            return state.get("Pid", -1)
        return -1

    def _check_shell(self):
        """Verify if shell is alive and
           try to restart if needed"""
        if self._is_container_running():
            if self.shell:
                self.shell.poll()
                if self.shell.returncode is not None:
                    debug("*** Shell died for docker host \'%s\'!\n" % self.name )
                    self.shell = None
                    debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                    self.startShell()
            else:
                debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                self.startShell()
        else:
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            if self.shell:
                self.shell = None

    def _is_container_running(self):
        """Verify if container is alive"""
        container_list = self.dcli.containers(filters={"id": self.did, "status": "running"})
        if len(container_list) == 0:
            return False;
        return True

    def _check_image_exists(self, imagename, pullImage=False):
        # split tag from repository if a tag is specified
        if ":" in imagename:
            #If two :, then the first is to specify a port. Otherwise, it must be a tag
            slices = imagename.split(":")
            repo = ":".join(slices[0:-1])
            tag = slices[-1]
        else:
            repo = imagename
            tag = "latest"

        if self._image_exists(repo, tag):
            return True

        # image not found
        if pullImage:
            if self._pull_image(repo, tag):
                info('*** Download of "%s:%s" successful\n' % (repo, tag))
                return True
        # we couldn't find the image
        return False

    def _image_exists(self, repo, tag):
        """
        Checks if the repo:tag image exists locally
        :return: True if the image exists locally. Else false.
        """
        # filter by repository
        images = self.dcli.images(repo)
        imageName = "%s:%s" % (repo, tag)

        for image in images:
            if 'RepoTags' in image:
                if image['RepoTags'] is None:
                    return False
                if imageName in image['RepoTags']:
                    return True
        return False

    def _pull_image(self, repository, tag):
        """
        :return: True if pull was successful. Else false.
        """
        try:
            info('*** Image "%s:%s" not found. Trying to load the image. \n' % (repository, tag))
            info('*** This can take some minutes...\n')

            message = ""
            for line in self.dcli.pull(repository, tag, stream=True):
                # Collect output of the log for enhanced error feedback
                message = message + json.dumps(json.loads(line), indent=4)

        except:
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
        if not self._image_exists(repository, tag):
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
            return False
        return True

    def update_resources(self, **kwargs):
        """
        Update the container's resources using the docker.update function
        re-using the same parameters:
        Args:
           blkio_weight
           cpu_period, cpu_quota, cpu_shares
           cpuset_cpus
           cpuset_mems
           mem_limit
           mem_reservation
           memswap_limit
           kernel_memory
           restart_policy
        see https://docs.docker.com/engine/reference/commandline/update/
        or API docs: https://docker-py.readthedocs.io/en/stable/api.html#module-docker.api.container
        :return:
        """

        self.resources.update(kwargs)
        # filter out None values to avoid errors
        resources_filtered = {res:self.resources[res] for res in self.resources if self.resources[res] is not None}
        info("{1}: update resources {0}\n".format(resources_filtered, self.name))
        self.dcli.update_container(self.dc, **resources_filtered)

    def updateCpuLimit(self, cpu_quota=-1, cpu_period=-1, cpu_shares=-1, cores=None):
        """
        Update CPU resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.
        Args:
            cpu_quota: cfs quota us
            cpu_period: cfs period us
            cpu_shares: cpu shares
            cores: specifies which cores should be accessible for the container e.g. "0-2,16" represents
                Cores 0, 1, 2, and 16
        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt

        # also negative values can be set for cpu_quota (uncontrained setting)
        # just check if value is a valid integer
        if isinstance(cpu_quota, int):
            self.resources['cpu_quota'] = self.cgroupSet("cfs_quota_us", cpu_quota)
        if cpu_period >= 0:
            self.resources['cpu_period'] = self.cgroupSet("cfs_period_us", cpu_period)
        if cpu_shares >= 0:
            self.resources['cpu_shares'] = self.cgroupSet("shares", cpu_shares)
        if cores:
            self.dcli.update_container(self.dc, cpuset_cpus=cores)
            # quota, period ad shares can also be set by this line. Usable for future work.

    def updateMemoryLimit(self, mem_limit=-1, memswap_limit=-1):
        """
        Update Memory resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.

        Args:
            mem_limit: memory limit in bytes
            memswap_limit: swap limit in bytes

        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt
        if mem_limit >= 0:
            self.resources['mem_limit'] = self.cgroupSet("limit_in_bytes", mem_limit, resource="memory")
        if memswap_limit >= 0:
            self.resources['memswap_limit'] = self.cgroupSet("memsw.limit_in_bytes", memswap_limit, resource="memory")


    def cgroupSet(self, param, value, resource='cpu'):
        """
        Directly manipulate the resource settings of the Docker container's cgrpup.
        Args:
            param: parameter to set, e.g., cfs_quota_us
            value: value to set
            resource: resource name: cpu

        Returns: value that was set

        """
        cmd = 'cgset -r %s.%s=%s docker/%s' % (
            resource, param, value, self.did)
        debug(cmd + "\n")
        try:
            check_output(cmd, shell=True)
        except:
            error("Problem writing cgroup setting %r\n" % cmd)
            return
        nvalue = int(self.cgroupGet(param, resource))
        if nvalue != value:
            error('*** error: cgroupSet: %s set to %s instead of %s\n'
                  % (param, nvalue, value))
        return nvalue

    def cgroupGet(self, param, resource='cpu'):
        """
        Read cgroup values.
        Args:
            param: parameter to read, e.g., cfs_quota_us
            resource: resource name: cpu / memory

        Returns: value

        """
        cmd = 'cgget -r %s.%s docker/%s' % (
            resource, param, self.did)
        try:
            return int(check_output(cmd, shell=True).split()[-1])
        except:
            error("Problem reading cgroup info: %r\n" % cmd)
            return -1


class DockerSta(Station):
    """Node that represents a docker container.
    This part is inspired by:
    http://techandtrains.com/2014/08/21/docker-container-as-mininet-host/
    We use the docker-py client library to control docker.
    """

    def __init__(self, name, dimage=None, dcmd=None, did=None, **kwargs):
        """
        Creates a Docker container as Mininet host.

        Resource limitations based on CFS scheduler:
        * cpu.cfs_quota_us: the total available run-time within a period (in microseconds)
        * cpu.cfs_period_us: the length of a period (in microseconds)
        (https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt)

        Default Docker resource limitations:
        * cpu_shares: Relative amount of max. avail CPU for container
            (not a hard limit, e.g. if only one container is busy and the rest idle)
            e.g. usage: d1=4 d2=6 <=> 40% 60% CPU
        * cpuset_cpus: Bind containers to CPU 0 = cpu_1 ... n-1 = cpu_n (string: '0,2')
        * mem_limit: Memory limit (format: <number>[<unit>], where unit = b, k, m or g)
        * memswap_limit: Total limit = memory + swap

        All resource limits can be updated at runtime! Use:
        * updateCpuLimits(...)
        * updateMemoryLimits(...)
        """
        self.dimage = dimage
        self.dnameprefix = "mn"
        self.dcmd = dcmd if dcmd is not None else "/bin/bash"
        self.dc = None  # pointer to the dict containing 'Id' and 'Warnings' keys of the container
        self.dcinfo = None
        self.wintfs = {}
        self.wports = {}
        self.did = did  # Id of running container
        #  let's store our resource limits to have them available through the
        #  Mininet API later on
        defaults = { 'cpu_quota': -1,
                     'cpu_period': None,
                     'cpu_shares': None,
                     'cpuset_cpus': None,
                     'mem_limit': None,
                     'memswap_limit': None,
                     'environment': {},
                     'volumes': [],  # use ["/home/user1/:/mnt/vol2:rw"]
                     'tmpfs': [], # use ["/home/vol1/:size=3G,uid=1000"]
                     'network_mode': None,
                     'privileged': False,
                     'publish_all_ports': True,
                     'port_bindings': {},
                     'ports': [],
                     'dns': [],
                     'ipc_mode': None,
                     'devices': [],
                     'cap_add': ['net_admin'],  # we need this to allow mininet network setup
                     #'storage_opt': None,
                     'sysctls': {}
                     }
        defaults.update( kwargs )

        # keep resource in a dict for easy update during container lifetime
        self.resources = dict(
            cpu_quota=defaults['cpu_quota'],
            cpu_period=defaults['cpu_period'],
            cpu_shares=defaults['cpu_shares'],
            cpuset_cpus=defaults['cpuset_cpus'],
            mem_limit=defaults['mem_limit'],
            memswap_limit=defaults['memswap_limit']
        )

        self.volumes = defaults['volumes']
        self.tmpfs = defaults['tmpfs']
        self.environment = {} if defaults['environment'] is None else defaults['environment']
        # setting PS1 at "docker run" may break the python docker api (update_container hangs...)
        # self.environment.update({"PS1": chr(127)})  # CLI support
        self.network_mode = defaults['network_mode']
        self.privileged = defaults['privileged']
        self.publish_all_ports = defaults['publish_all_ports']
        self.port_bindings = defaults['port_bindings']
        self.dns = defaults['dns']
        self.ipc_mode = defaults['ipc_mode']
        self.devices = defaults['devices']
        self.cap_add = defaults['cap_add']
        self.sysctls = defaults['sysctls']
        #self.storage_opt = defaults['storage_opt']

        # setup docker client
        # self.dcli = docker.APIClient(base_url='unix://var/run/docker.sock')
        self.dcli = docker.from_env().api

        # pull image if it does not exist
        if self.dimage:
            self._check_image_exists(dimage, True)

        # for DEBUG
        debug("Created docker container object %s\n" % name)
        debug("image: %s\n" % str(self.dimage))
        debug("dcmd: %s\n" % str(self.dcmd))
        info("%s: kwargs %s\n" % (name, str(kwargs)))

        # creats host config for container
        # see: https://docker-py.readthedocs.org/en/latest/hostconfig/
        hc = self.dcli.create_host_config(
            network_mode=self.network_mode,
            privileged=self.privileged,
            binds=self.volumes,
            tmpfs=self.tmpfs,
            publish_all_ports=self.publish_all_ports,
            port_bindings=self.port_bindings,
            mem_limit=self.resources.get('mem_limit'),
            cpuset_cpus=self.resources.get('cpuset_cpus'),
            dns=self.dns,
            ipc_mode=self.ipc_mode,  # string
            devices=self.devices,  # see docker-py docu
            cap_add=self.cap_add,  # see docker-py docu
            sysctls=self.sysctls,  # see docker-py docu
            #storage_opt=self.storage_opt
        )

        if kwargs.get("rm", False):
            container_list = self.dcli.containers(all=True)
            for container in container_list:
                for container_name in container.get("Names", []):
                    if "%s.%s" % (self.dnameprefix, name) in container_name:
                        self.dcli.remove_container(container="%s.%s" % (self.dnameprefix, name), force=True)
                        break

        if self.did:
            self.dc = {'Id': '{}'.format(self.did), 'Warnings': []}
            self.existing_container = 1
        else:
            # create new docker container
            self.dc = self.dcli.create_container(
                name="%s.%s" % (self.dnameprefix, name),
                image=self.dimage,
                command=self.dcmd,
                entrypoint=list(),  # overwrite (will be executed manually at the end)
                stdin_open=True,  # keep container open
                tty=True,  # allocate pseudo tty
                environment=self.environment,
                #network_disabled=True,  # docker stats breaks if we disable the default network
                host_config=hc,
                ports=defaults['ports'],
                labels=['com.containernet'],
                volumes=[self._get_volume_mount_name(v) for v in self.volumes if self._get_volume_mount_name(v) is not None],
                hostname=name
            )

        # start the container
        self.dcli.start(self.dc)
        debug("Docker container %s started\n" % name)

        # fetch information about new container
        self.dcinfo = self.dcli.inspect_container(self.dc)
        self.did = self.dcinfo.get("Id")

        # call original Node.__init__
        Node.__init__(self, name, **kwargs)

        # let's initially set our resource limits
        self.update_resources(**self.resources)

    def start(self):
        # Containernet ignores the CMD field of the Dockerfile.
        # Lets try to load it here and manually execute it once the
        # container is started and configured by Containernet:
        cmd_field = self.get_cmd_field(self.dimage)
        entryp_field = self.get_entrypoint_field(self.dimage)
        if entryp_field is not None:
            if cmd_field is None:
                cmd_field = list()
            # clean up cmd_field
            try:
                cmd_field.remove(u'/bin/sh')
                cmd_field.remove(u'-c')
            except ValueError:
                pass
            # we just add the entryp. commands to the beginning:
            cmd_field = entryp_field + cmd_field
        if cmd_field is not None:
            cmd_field.append("> /dev/pts/0 2>&1")  # make output available to docker logs
            cmd_field.append("&")  # put to background (works, but not nice)
            info("{}: running CMD: {}\n".format(self.name, cmd_field))
            self.cmd(" ".join(cmd_field))

    def get_cmd_field(self, imagename):
        """
        Try to find the original CMD command of the Dockerfile
        by inspecting the Docker image.
        Returns list from CMD field if it is different from
        a single /bin/bash command which Containernet executes
        anyhow.
        """
        try:
            imgd = self.dcli.inspect_image(imagename)
            cmd = imgd.get("Config", {}).get("Cmd")
            assert isinstance(cmd, list)
            # filter the default case: a single "/bin/bash"
            if "/bin/bash" in cmd and len(cmd) == 1:
                return None
            return cmd
        except BaseException as ex:
            error("Error during image inspection of {}:{}"
                  .format(imagename, ex))
        return None

    def get_entrypoint_field(self, imagename):
        """
        Try to find the original ENTRYPOINT command of the Dockerfile
        by inspecting the Docker image.
        Returns list or None.
        """
        try:
            imgd = self.dcli.inspect_image(imagename)
            ep = imgd.get("Config", {}).get("Entrypoint")
            if isinstance(ep, list) and len(ep) < 1:
                return None
            return ep
        except BaseException as ex:
            error("Error during image inspection of {}:{}"
                  .format(imagename, ex))
        return None

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
        # mnexec: (c)lose descriptors, (d)etach from tty,
        # (p)rint pid, and run in (n)amespace
        # opts = '-cd' if mnopts is None else mnopts
        # if self.inNamespace:
        #     opts += 'n'
        # bash -i: force interactive
        # -s: pass $* to shell, and make process easy to find in ps
        # prompt is set to sentinel chr( 127 )
        if hasattr(self, 'existing_container'):
            cmd = ['docker', 'exec', '-it', '%s' % self.did, 'env', 'PS1=' + chr(127),
                   'bash', '--norc', '-is', 'mininet:' + self.name]
        else:
            cmd = [ 'docker', 'exec', '-it',  '%s.%s' % ( self.dnameprefix, self.name ), 'env', 'PS1=' + chr( 127 ),
                    'bash', '--norc', '-is', 'mininet:' + self.name ]
        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        self.master, self.slave = pty.openpty()
        self.shell = self._popen( cmd, stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                  close_fds=False )
        self.stdin = os.fdopen( self.master, 'r' )
        self.stdout = self.stdin
        self.pid = self._get_pid()
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read( 1024 )
            if data[ -1 ] == chr( 127 ):
                break
            self.pollOut.poll()
        self.waiting = False
        # +m: disable job control notification
        self.cmd( 'unset HISTFILE; stty -echo; set +m' )

    def _get_volume_mount_name(self, volume_str):
        """ Helper to extract mount names from volume specification strings """
        parts = volume_str.split(":")
        if len(parts) < 3:
            return None
        return parts[1]

    def terminate( self ):
        """ Stop docker container """
        if not self._is_container_running():
            return
        try:
            if not hasattr(self, 'existing_container'):
                self.dcli.remove_container(self.dc, force=True, v=True)
        except docker.errors.APIError:
            warn("Warning: API error during container removal.\n")

        self.cleanup()

    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete."""
        self._check_shell()
        if not self.shell:
            return
        Station.sendCmd( self, *args, **kwargs )

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in node's namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        if not self._is_container_running():
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            return
        mncmd = ["docker", "exec", "-t", "%s.%s" % (self.dnameprefix, self.name)]
        return Node.popen( self, *args, mncmd=mncmd, **kwargs )

    def cmd(self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )
        self.sendCmd( *args, **kwargs )
        return self.waitOutput( verbose )

    def _get_pid(self):
        state = self.dcinfo.get("State", None)
        if state:
            return state.get("Pid", -1)
        return -1

    def _check_shell(self):
        """Verify if shell is alive and
           try to restart if needed"""
        if self._is_container_running():
            if self.shell:
                self.shell.poll()
                if self.shell.returncode is not None:
                    debug("*** Shell died for docker host \'%s\'!\n" % self.name )
                    self.shell = None
                    debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                    self.startShell()
            else:
                debug("*** Restarting Shell of docker host \'%s\'!\n" % self.name )
                self.startShell()
        else:
            error( "ERROR: Can't connect to Container \'%s\'' for docker host \'%s\'!\n" % (self.did, self.name) )
            if self.shell:
                self.shell = None

    def _is_container_running(self):
        """Verify if container is alive"""
        container_list = self.dcli.containers(filters={"id": self.did, "status": "running"})
        if len(container_list) == 0:
            return False;
        return True

    def _check_image_exists(self, imagename, pullImage=False):
        # split tag from repository if a tag is specified
        if ":" in imagename:
            #If two :, then the first is to specify a port. Otherwise, it must be a tag
            slices = imagename.split(":")
            repo = ":".join(slices[0:-1])
            tag = slices[-1]
        else:
            repo = imagename
            tag = "latest"

        if self._image_exists(repo, tag):
            return True

        # image not found
        if pullImage:
            if self._pull_image(repo, tag):
                info('*** Download of "%s:%s" successful\n' % (repo, tag))
                return True
        # we couldn't find the image
        return False

    def _image_exists(self, repo, tag):
        """
        Checks if the repo:tag image exists locally
        :return: True if the image exists locally. Else false.
        """
        # filter by repository
        images = self.dcli.images(repo)
        imageName = "%s:%s" % (repo, tag)

        for image in images:
            if 'RepoTags' in image:
                if image['RepoTags'] is None:
                    return False
                if imageName in image['RepoTags']:
                    return True
        return False

    def _pull_image(self, repository, tag):
        """
        :return: True if pull was successful. Else false.
        """
        try:
            info('*** Image "%s:%s" not found. Trying to load the image. \n' % (repository, tag))
            info('*** This can take some minutes...\n')

            message = ""
            for line in self.dcli.pull(repository, tag, stream=True):
                # Collect output of the log for enhanced error feedback
                message = message + json.dumps(json.loads(line), indent=4)

        except:
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
        if not self._image_exists(repository, tag):
            error('*** error: _pull_image: %s:%s failed.' % (repository, tag)
                  + message)
            return False
        return True

    def update_resources(self, **kwargs):
        """
        Update the container's resources using the docker.update function
        re-using the same parameters:
        Args:
           blkio_weight
           cpu_period, cpu_quota, cpu_shares
           cpuset_cpus
           cpuset_mems
           mem_limit
           mem_reservation
           memswap_limit
           kernel_memory
           restart_policy
        see https://docs.docker.com/engine/reference/commandline/update/
        or API docs: https://docker-py.readthedocs.io/en/stable/api.html#module-docker.api.container
        :return:
        """

        self.resources.update(kwargs)
        # filter out None values to avoid errors
        resources_filtered = {res:self.resources[res] for res in self.resources if self.resources[res] is not None}
        info("{1}: update resources {0}\n".format(resources_filtered, self.name))
        self.dcli.update_container(self.dc, **resources_filtered)

    def updateCpuLimit(self, cpu_quota=-1, cpu_period=-1, cpu_shares=-1, cores=None):
        """
        Update CPU resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.
        Args:
            cpu_quota: cfs quota us
            cpu_period: cfs period us
            cpu_shares: cpu shares
            cores: specifies which cores should be accessible for the container e.g. "0-2,16" represents
                Cores 0, 1, 2, and 16
        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt

        # also negative values can be set for cpu_quota (uncontrained setting)
        # just check if value is a valid integer
        if isinstance(cpu_quota, int):
            self.resources['cpu_quota'] = self.cgroupSet("cfs_quota_us", cpu_quota)
        if cpu_period >= 0:
            self.resources['cpu_period'] = self.cgroupSet("cfs_period_us", cpu_period)
        if cpu_shares >= 0:
            self.resources['cpu_shares'] = self.cgroupSet("shares", cpu_shares)
        if cores:
            self.dcli.update_container(self.dc, cpuset_cpus=cores)
            # quota, period ad shares can also be set by this line. Usable for future work.

    def updateMemoryLimit(self, mem_limit=-1, memswap_limit=-1):
        """
        Update Memory resource limitations.
        This method allows to update resource limitations at runtime by bypassing the Docker API
        and directly manipulating the cgroup options.

        Args:
            mem_limit: memory limit in bytes
            memswap_limit: swap limit in bytes

        """
        # see https://www.kernel.org/doc/Documentation/scheduler/sched-bwc.txt
        if mem_limit >= 0:
            self.resources['mem_limit'] = self.cgroupSet("limit_in_bytes", mem_limit, resource="memory")
        if memswap_limit >= 0:
            self.resources['memswap_limit'] = self.cgroupSet("memsw.limit_in_bytes", memswap_limit, resource="memory")

    def cgroupSet(self, param, value, resource='cpu'):
        """
        Directly manipulate the resource settings of the Docker container's cgrpup.
        Args:
            param: parameter to set, e.g., cfs_quota_us
            value: value to set
            resource: resource name: cpu

        Returns: value that was set

        """
        cmd = 'cgset -r %s.%s=%s docker/%s' % (
            resource, param, value, self.did)
        debug(cmd + "\n")
        try:
            check_output(cmd, shell=True)
        except:
            error("Problem writing cgroup setting %r\n" % cmd)
            return
        nvalue = int(self.cgroupGet(param, resource))
        if nvalue != value:
            error('*** error: cgroupSet: %s set to %s instead of %s\n'
                  % (param, nvalue, value))
        return nvalue

    def cgroupGet(self, param, resource='cpu'):
        """
        Read cgroup values.
        Args:
            param: parameter to read, e.g., cfs_quota_us
            resource: resource name: cpu / memory

        Returns: value

        """
        cmd = 'cgget -r %s.%s docker/%s' % (
            resource, param, self.did)
        try:
            return int(check_output(cmd, shell=True).split()[-1])
        except:
            error("Problem reading cgroup info: %r\n" % cmd)
            return -1


class Switch(Node):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    portBase = 1  # Switches start with port 1 in OpenFlow
    dpidLen = 16  # digits in dpid passed to switch

    def __init__( self, name, dpid=None, opts='', listenPort=None, **params):
        """dpid: dpid hex string (or None to derive from name, e.g. s1 -> 1)
           opts: additional switch options
           listenPort: port to listen on for dpctl connections"""
        Node.__init__( self, name, **params )
        self.dpid = self.defaultDpid( dpid )
        self.opts = opts
        self.listenPort = listenPort
        if not self.inNamespace:
            self.controlIntf = Intf( 'lo', self, port=0 )

    def defaultDpid( self, dpid=None ):
        "Return correctly formatted dpid from dpid or switch name (s1 -> 1)"
        if dpid:
            # Remove any colons and make sure it's a good hex number
            dpid = dpid.replace( ':', '' )
            assert len( dpid ) <= self.dpidLen and int( dpid, 16 ) >= 0
        else:
            # Use hex of the first number in the switch name
            nums = re.findall( r'\d+', self.name )
            if nums:
                dpid = hex( int( nums[ 0 ] ) )[ 2: ]
            else:
                self.terminate()  # Python 3.6 crash workaround
                raise Exception( 'Unable to derive default datapath ID - '
                                 'please either specify a dpid or use a '
                                 'canonical switch name such as s23.' )
        return '0' * ( self.dpidLen - len( dpid ) ) + dpid

    def defaultIntf( self ):
        "Return control interface"
        if self.controlIntf:
            return self.controlIntf
        else:
            return Node.defaultIntf( self )

    def sendCmd( self, *cmd, **kwargs ):
        """Send command to Node.
           cmd: string"""
        kwargs.setdefault( 'printPid', False )
        if not self.execed:
            return Node.sendCmd( self, *cmd, **kwargs )
        else:
            error( '*** Error: %s has execed and cannot accept commands' %
                   self.name )

    def connected( self ):
        "Is the switch connected to a controller? (override this method)"
        # Assume that we are connected by default to whatever we need to
        # be connected to. This should be overridden by any OpenFlow
        # switch, but not by a standalone bridge.
        debug( 'Assuming', repr( self ), 'is connected to a controller\n' )
        return True

    def stop( self, deleteIntfs=True ):
        """Stop switch
           deleteIntfs: delete interfaces? (True)"""
        if deleteIntfs:
            self.deleteIntfs()
        self.terminate()

    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )


class UserSwitch( Switch ):
    "User-space switch."

    dpidLen = 12

    def __init__( self, name, dpopts='--no-slicing', **kwargs ):
        """Init.
           name: name for the switch
           dpopts: additional arguments to ofdatapath (--no-slicing)"""
        Switch.__init__( self, name, **kwargs )
        pathCheck( 'ofdatapath', 'ofprotocol',
                   moduleName='the OpenFlow reference user switch' +
                              '(openflow.org)' )
        if self.listenPort:
            self.opts += ' --listen=ptcp:%i ' % self.listenPort
        else:
            self.opts += ' --listen=punix:/tmp/%s.listen' % self.name
        self.dpopts = dpopts

    @classmethod
    def setup( cls ):
        "Ensure any dependencies are loaded; if not, try to load them."
        if not os.path.exists( '/dev/net/tun' ):
            moduleDeps( add=TUN )

    def dpctl( self, *args ):
        "Run dpctl command"
        listenAddr = None
        if not self.listenPort:
            listenAddr = 'unix:/tmp/%s.listen' % self.name
        else:
            listenAddr = 'tcp:127.0.0.1:%i' % self.listenPort
        return self.cmd( 'dpctl ' + ' '.join( args ) +
                         ' ' + listenAddr )

    def connected( self ):
        "Is the switch connected to a controller?"
        status = self.dpctl( 'status' )
        return ( 'remote.is-connected=true' in status and
                 'local.is-connected=true' in status )

    @staticmethod
    def TCReapply( intf ):
        """Unfortunately user switch and Mininet are fighting
           over tc queuing disciplines. To resolve the conflict,
           we re-create the user switch's configuration, but as a
           leaf of the TCIntf-created configuration."""
        if isinstance( intf, TCIntf ):
            ifspeed = 10000000000  # 10 Gbps
            minspeed = ifspeed * 0.001

            res = intf.config( **intf.params )

            if res is None:  # link may not have TC parameters
                return

            # Re-add qdisc, root, and default classes user switch created, but
            # with new parent, as setup by Mininet's TCIntf
            parent = res['parent']
            intf.tc( "%s qdisc add dev %s " + parent +
                     " handle 1: htb default 0xfffe" )
            intf.tc( "%s class add dev %s classid 1:0xffff parent 1: htb rate "
                     + str(ifspeed) )
            intf.tc( "%s class add dev %s classid 1:0xfffe parent 1:0xffff " +
                     "htb rate " + str(minspeed) + " ceil " + str(ifspeed) )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ofd,ofp}.log.
           controllers: list of controller objects"""
        # Add controllers
        clist = ','.join( [ 'tcp:%s:%d' % ( c.IP(), c.port )
                            for c in controllers ] )
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        intfs = [ str( i ) for i in self.intfList() if not i.IP() ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
                  ' punix:/tmp/' + self.name + ' -d %s ' % self.dpid +
                  self.dpopts +
                  ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmd( 'ofprotocol unix:/tmp/' + self.name +
                  ' ' + clist +
                  ' --fail=closed ' + self.opts +
                  ' 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        if "no-slicing" not in self.dpopts:
            # Only TCReapply if slicing is enable
            sleep(1)  # Allow ofdatapath to start before re-arranging qdisc's
            for intf in self.intfList():
                if not intf.IP():
                    self.TCReapply( intf )

    def stop( self, deleteIntfs=True ):
        """Stop OpenFlow reference user datapath.
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'kill %ofdatapath' )
        self.cmd( 'kill %ofprotocol' )
        super( UserSwitch, self ).stop( deleteIntfs )


class OVSSwitch( Switch ):
    "Open vSwitch switch. Depends on ovs-vsctl."

    def __init__( self, name, failMode='secure', datapath='kernel',
                  inband=False, protocols=None,
                  reconnectms=1000, stp=False, batch=False, **params ):
        """name: name for switch
           failMode: controller loss behavior (secure|standalone)
           datapath: userspace or kernel mode (kernel|user)
           inband: use in-band control (False)
           protocols: use specific OpenFlow version(s) (e.g. OpenFlow13)
                      Unspecified (or old OVS version) uses OVS default
           reconnectms: max reconnect timeout in ms (0/None for default)
           stp: enable STP (False, requires failMode=standalone)
           batch: enable batch startup (False)"""
        Switch.__init__( self, name, **params )
        self.failMode = failMode
        self.datapath = datapath
        self.inband = inband
        self.protocols = protocols
        self.reconnectms = reconnectms
        self.stp = stp
        self._uuids = []  # controller UUIDs
        self.batch = batch
        self.commands = []  # saved commands for batch startup

        # add a prefix to the name of the deployed switch, to find it back easier later
        prefix = params.get('prefix', '')
        self.deployed_name = prefix + name


    @classmethod
    def setup( cls ):
        "Make sure Open vSwitch is installed and working"
        pathCheck( 'ovs-vsctl',
                   moduleName='Open vSwitch (openvswitch.org)')
        # This should no longer be needed, and it breaks
        # with OVS 1.7 which has renamed the kernel module:
        #  moduleDeps( subtract=OF_KMOD, add=OVS_KMOD )
        out, err, exitcode = errRun( 'ovs-vsctl -t 1 show' )
        if exitcode:
            error( out + err +
                   'ovs-vsctl exited with code %d\n' % exitcode +
                   '*** Error connecting to ovs-db with ovs-vsctl\n'
                   'Make sure that Open vSwitch is installed, '
                   'that ovsdb-server is running, and that\n'
                   '"ovs-vsctl show" works correctly.\n'
                   'You may wish to try '
                   '"service openvswitch-switch start".\n' )
            exit( 1 )
        version = quietRun( 'ovs-vsctl --version' )
        cls.OVSVersion = findall( r'\d+\.\d+', version )[ 0 ]

    @classmethod
    def isOldOVS( cls ):
        "Is OVS ersion < 1.10?"
        return ( StrictVersion( cls.OVSVersion ) <
                 StrictVersion( '1.10' ) )

    def dpctl( self, *args ):
        "Run ovs-ofctl command"
        return self.cmd( 'ovs-ofctl', args[ 0 ], self.deployed_name, *args[ 1: ] )

    def vsctl( self, *args, **kwargs ):
        "Run ovs-vsctl command (or queue for later execution)"
        if self.batch:
            cmd = ' '.join( str( arg ).strip() for arg in args )
            self.commands.append( cmd )
        else:
            return self.cmd( 'ovs-vsctl', *args, **kwargs )

    @staticmethod
    def TCReapply( intf ):
        """Unfortunately OVS and Mininet are fighting
           over tc queuing disciplines. As a quick hack/
           workaround, we clear OVS's and reapply our own."""
        if isinstance( intf, TCIntf ):
            intf.config( **intf.params )

    def attach( self, intf ):
        "Connect a data port"
        self.vsctl( 'add-port', self.deployed_name, intf )
        self.cmd( 'ifconfig', intf, 'up' )
        self.TCReapply( intf )

    def attachInternalIntf(self, intf_name, net):
        """Add an interface of type:internal to the ovs switch
           and add routing entry to host"""
        self.vsctl('add-port', self.deployed_name, intf_name, '--', 'set',
                   ' interface', intf_name, 'type=internal')
        int_intf = Intf(intf_name, node=self.deployed_name)
        #self.addIntf(int_intf, moveIntfFn=None)
        self.cmd('ip route add', net, 'dev', intf_name)

        return self.nameToIntf[intf_name]

    def detach( self, intf ):
        "Disconnect a data port"
        self.vsctl( 'del-port', self.deployed_name, intf )

    def controllerUUIDs( self, update=False ):
        """Return ovsdb UUIDs for our controllers
           update: update cached value"""
        if not self._uuids or update:
            controllers = self.cmd( 'ovs-vsctl -- get Bridge', self.deployed_name,
                                    'Controller' ).strip()
            if controllers.startswith( '[' ) and controllers.endswith( ']' ):
                controllers = controllers[ 1 : -1 ]
                if controllers:
                    self._uuids = [ c.strip()
                                    for c in controllers.split( ',' ) ]
        return self._uuids

    def connected( self ):
        "Are we connected to at least one of our controllers?"
        for uuid in self.controllerUUIDs():
            if 'true' in self.vsctl( '-- get Controller',
                                     uuid, 'is_connected' ):
                return True
        return self.failMode == 'standalone'

    def intfOpts( self, intf ):
        "Return OVS interface options for intf"
        opts = ''
        if not self.isOldOVS():
            # ofport_request is not supported on old OVS
            opts += ' ofport_request=%s' % self.ports[ intf ]
            # Patch ports don't work well with old OVS
            if isinstance( intf, OVSIntf ):
                intf1, intf2 = intf.link.intf1, intf.link.intf2
                peer = intf1 if intf1 != intf else intf2
                opts += ' type=patch options:peer=%s' % peer
        return '' if not opts else ' -- set Interface %s' % intf + opts

    def bridgeOpts( self ):
        "Return OVS bridge options"
        opts = ( ' other_config:datapath-id=%s' % self.dpid +
                 ' fail_mode=%s' % self.failMode )
        if not self.inband:
            opts += ' other-config:disable-in-band=true'
        if self.datapath == 'user':
            opts += ' datapath_type=netdev'
        if self.protocols and not self.isOldOVS():
            opts += ' protocols=%s' % self.protocols
        if self.stp and self.failMode == 'standalone':
            opts += ' stp_enable=true'
        opts += ' other-config:dp-desc=%s' % self.name
        return opts

    def start( self, controllers ):
        "Start up a new OVS OpenFlow switch using ovs-vsctl"
        if self.inNamespace:
            raise Exception(
                'OVS kernel switch does not work in a namespace' )
        int( self.dpid, 16 )  # DPID must be a hex string
        # Command to add interfaces
        intfs = ''.join( ' -- add-port %s %s' % ( self.deployed_name, intf ) +
                         self.intfOpts( intf )
                         for intf in self.intfList()
                         if self.ports[ intf ] and not intf.IP() )
        # Command to create controller entries
        clist = [ ( self.deployed_name + c.name, '%s:%s:%d' %
                  ( c.protocol, c.IP(), c.port ) )
                  for c in controllers ]
        if self.listenPort:
            clist.append( ( self.deployed_name + '-listen',
                            'ptcp:%s' % self.listenPort ) )
        ccmd = '-- --id=@%s create Controller target=\\"%s\\"'
        if self.reconnectms:
            ccmd += ' max_backoff=%d' % self.reconnectms
        cargs = ' '.join( ccmd % ( name, target )
                          for name, target in clist )
        # Controller ID list
        cids = ','.join( '@%s' % name for name, _target in clist )
        # Try to delete any existing bridges with the same name
        if not self.isOldOVS():
            cargs += ' -- --if-exists del-br %s' % self.deployed_name
        # One ovs-vsctl command to rule them all!
        self.vsctl( cargs +
                    ' -- add-br %s' % self.deployed_name +
                    ' -- set bridge %s controller=[%s]' % ( self.deployed_name, cids  ) +
                    self.bridgeOpts() +
                    intfs )
        # If necessary, restore TC config overwritten by OVS
        if not self.batch:
            for intf in self.intfList():
                self.TCReapply( intf )

    # This should be ~ int( quietRun( 'getconf ARG_MAX' ) ),
    # but the real limit seems to be much lower
    argmax = 128000

    @classmethod
    def batchStartup( cls, switches, run=errRun ):
        """Batch startup for OVS
           switches: switches to start up
           run: function to run commands (errRun)"""
        info( '...' )
        cmds = 'ovs-vsctl'
        for switch in switches:
            if switch.isOldOVS():
                # Ideally we'd optimize this also
                run( 'ovs-vsctl del-br %s' % switch )
            for cmd in switch.commands:
                cmd = cmd.strip()
                # Don't exceed ARG_MAX
                if len( cmds ) + len( cmd ) >= cls.argmax:
                    run( cmds, shell=True )
                    cmds = 'ovs-vsctl'
                cmds += ' ' + cmd
                switch.cmds = []
                switch.batch = False
        if cmds:
            run( cmds, shell=True )
        # Reapply link config if necessary...
        for switch in switches:
            for intf in switch.intfs.values():
                if isinstance( intf, TCIntf ):
                    intf.config( **intf.params )
        return switches

    def stop( self, deleteIntfs=True ):
        """Terminate OVS switch.
           deleteIntfs: delete interfaces? (True)"""
        self.cmd( 'ovs-vsctl del-br', self.deployed_name )
        if self.datapath == 'user':
            self.cmd( 'ip link del', self.deployed_name )
        super( OVSSwitch, self ).stop( deleteIntfs )

    @classmethod
    def batchShutdown( cls, switches, run=errRun ):
        "Shut down a list of OVS switches"
        delcmd = 'del-br %s'
        if switches and not switches[ 0 ].isOldOVS():
            delcmd = '--if-exists ' + delcmd
        # First, delete them all from ovsdb
        run( 'ovs-vsctl ' +
             ' -- '.join( delcmd % s.deployed_name for s in switches ), shell=True )
        # Next, shut down all of the processes
        pids = ' '.join( str( switch.pid ) for switch in switches )

        success = False
        while not success:
            try:
                run( 'kill -HUP ' + pids )
                success = True
            except select.error as e:
                # retry on interrupt
                if e[0] != errno.EINTR:
                    raise
        for switch in switches:
            switch.terminate()
            switch.shell = None
        return switches


OVSKernelSwitch = OVSSwitch

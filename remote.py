"""
Upload folders specified by config script to a target server via ssh.
Optionally run command on server and copy resulting files back to local machine.
"""

import paramiko
import configparser
import getpass
import os
import logging
import fnmatch
import click


def connect(server, username, password="", port=22, autoadd=False):
    """
    Open ssh connection to server.

    :param server: Server address.
    :param username: ssh username.
    :param password: Use public/private key auth. when password is empty.
    :param port: Port number.
    :param autoadd: If true, unknown hosts are automatically added.

    :returns: The paramiko ssh connection.
    """
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))

    if autoadd:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(server, port=port, username=username, password=password)

    return ssh


def deploy(srcDir, destDir, exclude, ssh):
    """
    Copies all files via sftp from srcDir to destDir on the target server.

    :param srcDir: Source directory to copy the files from.
    :param destDir: Destination directory relative to home folder.
    :param exclude: List of files and directories to exclude from copying.
    :param ssh: The open ssh session.
    """
    sftp = ssh.open_sftp()

    destDir = os.path.join(destDir, os.path.basename(srcDir))
    srcDir = os.path.abspath(srcDir)

    sumFiles = 0

    for dirpath, dirnames, filenames in os.walk(srcDir):
        remotePath = os.path.join(destDir, dirpath[len(srcDir) + 1:])

        # Exclude directories.
        dirnames[:] = [d for d in dirnames if d not in exclude]

        # Create directories.
        try:
            sftp.listdir(remotePath)
        except IOError:
            sftp.mkdir(remotePath)

        for filename in filenames:
            # Exclude files.
            for wildcard in exclude:
                if fnmatch.fnmatch(filename, wildcard):
                    break
            else:
                file = os.path.join(dirpath, filename)
                to = os.path.join(remotePath, filename)
                logging.info("Copy {} to {}.".format(file, to))
                sftp.put(file, to)
                sumFiles += 1
    sftp.close()

    print("Copied {} files.".format(sumFiles))


def runRemote(command, ssh):
    """
    Run command on the server and return stdout.

    :param command: String with command to run on server (can be multiple separated by ';').
    :param ssh: Open ssh connection.

    :returns: (out, err) stdout and stderr from remote call.
    """
    logging.info("Running remote command: {}.".format(command))

    stdin, stdout, stderr = ssh.exec_command(command)
    stdin.close()

    out = ''
    for i in stdout.readlines():
        out += i

    err = ''
    for i in stderr.readlines():
        err += i

    return out, err


def copyFromRemote(file, destDir, ssh):
    sftp = ssh.open_sftp()

    logging.info("Copy from remote: {} to {}.".format(file, destDir))
    sftp.get(file, destDir)

    sftp.close()


@click.command()
@click.option("--copy/--no-copy", default=True, help="Copy files to server.")
@click.option("--run/--no-run", default=False, help="Run remote script.")
@click.option("--usepw/--usekey", default=False, help="Ask for password or use key.")
@click.option("--copyback/--no-copyback", default=False, help="Copies after run files from remote to local.")
@click.option("--config", help="The config ini file.")
@click.option("--verbose", is_flag=True, help="Verbose output.")
def main(copy, run, usepw, copyback, config, verbose):
    if not config:
        raise ValueError("No config file specified. Use --config FILE to specify config file.")

    if verbose:
        logging.basicConfig(level=logging.INFO)

    parser = configparser.ConfigParser()

    if not parser.read(config):
        raise ValueError('Could not read config file.')

    destDir = parser['DEPLOY']['destDir']
    srcDir = parser['DEPLOY']['srcDir'].split(',')
    exclude = parser['DEPLOY']['exclude'].split(',')

    server = parser['SERVER']['name']
    username = parser['SERVER']['username']
    port = int(parser['SERVER']['port'])

    if usepw:
        password = getpass.getpass()
        ssh = connect(server, username, password, port)
    else:
        ssh = connect(server, username, port=port)

    if copy:
        print('Deploy ...')
        for dir in srcDir:
            logging.info("Deploy {} ...".format(dir))
            deploy(dir, destDir, exclude, ssh)

    if run:
        print('Run remote command ...')
        runDir = parser['RUN']['dir']
        runCmd = parser['RUN']['run'].split(',')

        cdCmd = ["cd " + destDir + "/" + runDir]

        out, err = runRemote(";".join(cdCmd + runCmd), ssh)

    if copyback:
        print('Copy back ...')

        copybackFiles = parser['COPY']['files'].split(',')
        destDirLocal = parser['COPY']['destDirLocal']

        for i in copybackFiles:
            copyFromRemote(os.path.join(destDir, i), os.path.join(destDirLocal, os.path.basename(i)), ssh)

    ssh.close()

    if run:
        print("STDOUT")
        print(out)
        print("STDERR")
        print(err)

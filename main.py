#!/usr/bin/python3

import subprocess
import re
import os
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

def log(message):
    print(datetime.now(), message)

class Notifier:
    def __init__(self, user, ip):
        self.user = user
        self.ip = ip

    def send_notification(self, message):
        os.system('ssh ' + self.user + '@' + self.ip + ' \'notify-send "' + message + '"\'')

sftp_password = os.environ['SFTP_PASSWORD']
sftp_path = os.environ['SFTP_PATH']
sftp_mount_point = os.environ['SFTP_MOUNT_DIR']

def make_backup(ip, user, config_path, encryption_password):
    log('Starting backup for ' + user + '@' + ip)

    log('Initialize notifier')
    notifier = Notifier(user, ip)

    notifier.send_notification('Starting backup')

    log('Retrieving backup config ' + config_path)
    tmp_config_file = '/tmp/' + ip + '.cfg'
    subprocess.getoutput('scp ' + user + '@' + ip + ':' + config_path + ' ' + tmp_config_file)
    log('Backup config retrieved')

    log('Building directory list')
    with open(tmp_config_file) as f:
        directories = list(map(lambda dir: dir.strip(), f.readlines()))
    log('Directory list: `' + ' '.join(directories) + '`')
    os.system('rm ' + tmp_config_file)

    backup_file = str(date.today()) + '.tar.gz'
    command = '"tar -czvf ~/Backups/' + backup_file + ' ' + ' '.join(directories) + '"'

    os.system('ssh ' + user + '@' + ip + ' "mkdir -p ~/Backups"')
    os.system('ssh ' + user + '@' + ip + ' ' + command)
    os.system('scp ' + user + '@' + ip + ':~/Backups/' + backup_file + ' /tmp/' + backup_file)

    notifier.send_notification('Backup completed, encrypting..')
    log('Backup completed, encrypting');
    
    os.system('echo "' + encryption_password + '" | gpg -c --batch -c --cipher-algo AES256 --no-symkey-cache --passphrase-fd 0 /tmp/' + backup_file)

    notifier.send_notification('Encrypting complete, uploading');
    log('Encrypting complete, uploading');

    os.system('rm /tmp/' + backup_file)
    backup_file += '.gpg'

    os.system('mkdir -p ' + sftp_mount_point)
    os.system('echo ' + sftp_password + ' | sshfs ' + sftp_path + ':/ ' + sftp_mount_point + ' -o password_stdin');

    storage_dir = sftp_mount_point + '/' + user + '@' + ip
    os.system('mkdir -p ' + storage_dir)

    files = list(filter(lambda file: file != '', subprocess.getoutput('ls -l ' + storage_dir + ' | awk \'{print $9}\'').split('\n')))

    while (len(files)) > 20:
        os.system('rm ' + storage_dir + '/' + files[0])
        files.pop(0)

    os.system('mv /tmp/' + backup_file + ' ' + storage_dir + '/' + backup_file)

    os.system('fusermount -u ' + sftp_mount_point)

log('Starting backup..')

users = os.environ['USERS'].split(',')
config_paths = os.environ['DIRECTORY_CONFIG_PATH'].split(',')
encryption_pws = os.environ['ENCRYPTION_PASS'].split(',')
ips = os.environ['IPS'].split(',')

amount_backups = len(config_paths)
log('Found ' + str(amount_backups) + ' configuration(s)')

if amount_backups != len(encryption_pws) or amount_backups != len(users) or amount_backups != len(ips):
    log('Invalid configuration, amount of configurations not consistent, exiting')
    exit(1)

for i in range(0, amount_backups):
    make_backup(ips[i], users[i], config_paths[i], encryption_pws[i])

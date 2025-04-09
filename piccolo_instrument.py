import os
import json
import paramiko
from scp import SCPClient

###
# TODO:
# - Add a connection test / Hello World as default
# - Remove ip, username, password from the class and only use the login file
# - Add a test for the login file and suggest json file creation and exmaple

class Instrument:
    def __init__(self, 
                 local_script, 
                 script_args=None, 
                 rp_dir="piccolo_testing", 
                 ):
        
        # Local and remote script information
        self.local_script = local_script
        self.script_args = script_args or []
        self.rp_dir = rp_dir

    def deploy_and_run(self):
        self._get_rp_login()       
        self._connect()
        remote_script = self._transfer()
        output, errors = self._run(remote_script)
        self.ssh.close()
        return output, errors

    def _get_rp_login(self):
        with open("redpitaya/rp_login.json", "r") as f:
            rp_login_json = json.load(f)

        self.ip = rp_login_json["ip"]
        self.username = rp_login_json["username"]
        self.password = rp_login_json["password"]
        return None
        
    def _connect(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.ip, username=self.username, password=self.password)
        self.ssh.exec_command(f"mkdir -p {self.rp_dir}")
        return None

    def _transfer(self):
        remote_path = os.path.join(self.rp_dir, os.path.basename(self.local_script))
        with SCPClient(self.ssh.get_transport()) as scp:
            scp.put(self.local_script, remote_path)
        return remote_path

    def _run(self, remote_path):
        args = " ".join(self.script_args)
        script = os.path.basename(remote_path)
        cmd = f'bash -l -c "cd {self.rp_dir} && sudo python3 {script} {args}"'
        _, stdout, stderr = self.ssh.exec_command(cmd, get_pty=True)
        return stdout.read().decode(), stderr.read().decode()

    
if __name__ == "__main__":
    instrument = Instrument(local_script="redpitaya/piccolo_rp.py", script_args=["--verbose", "--very_verbose"], rp_dir="piccolo_testing")

    try:
        rp_out, _ = instrument.deploy_and_run()
        print("////////// Red Pitaya Output //////////")
        print("///////////////////////////////////////")
        print(rp_out)
    except Exception as local_err:
        print(f"Error: {local_err}")
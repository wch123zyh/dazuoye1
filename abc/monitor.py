import paramiko
import re
import json
from datetime import datetime

def test_ssh_connection(ip, username, password, port=22):
    """测试SSH连接并获取基础信息"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=username, password=password, timeout=10)
        
        # 获取主机名
        stdin, stdout, stderr = ssh.exec_command('hostname')
        hostname = stdout.read().decode().strip()
        
        # 获取系统信息
        stdin, stdout, stderr = ssh.exec_command('lsb_release -d')
        os_info = stdout.read().decode().strip()
        if not os_info:
            stdin, stdout, stderr = ssh.exec_command('cat /etc/os-release | grep PRETTY_NAME')
            os_info = stdout.read().decode().strip()
        
        ssh.close()
        
        return {
            'success': True,
            'hostname': hostname,
            'os_info': os_info
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def collect_host_data(host):
    """采集单个主机的监控数据"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host['ip'], host['port'], host['username'], host['password'], timeout=10)
        
        # 获取CPU使用率 (Ubuntu兼容方式)
        stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep 'Cpu(s)'")
        cpu_line = stdout.read().decode()
        cpu_usage = parse_cpu_usage(cpu_line)
        
        # 获取内存使用率
        stdin, stdout, stderr = ssh.exec_command("free | grep Mem")
        mem_line = stdout.read().decode()
        mem_usage = parse_memory_usage(mem_line)
        
        # 获取磁盘使用率
        stdin, stdout, stderr = ssh.exec_command("df / | tail -1")
        disk_line = stdout.read().decode()
        disk_usage = parse_disk_usage(disk_line)
        
        # 获取系统负载
        stdin, stdout, stderr = ssh.exec_command("cat /proc/loadavg")
        load_data = stdout.read().decode().strip()
        load_1, load_5, load_15 = load_data.split()[:3]
        
        # 获取运行时间
        stdin, stdout, stderr = ssh.exec_command("uptime -p")
        uptime = stdout.read().decode().strip()
        
        # 获取进程数量
        stdin, stdout, stderr = ssh.exec_command("ps aux | wc -l")
        processes = int(stdout.read().decode().strip()) - 1
        
        ssh.close()
        
        return {
            'ip': host['ip'],
            'hostname': host.get('hostname', 'Unknown'),
            'cpu_usage': cpu_usage,
            'mem_usage': mem_usage,
            'disk_usage': disk_usage,
            'load_1': load_1,
            'load_5': load_5,
            'load_15': load_15,
            'uptime': uptime,
            'processes': processes,
            'status': 'online',
            'last_update': datetime.now().isoformat(),
            'error': None
        }
        
    except Exception as e:
        return {
            'ip': host['ip'],
            'hostname': host.get('hostname', 'Unknown'),
            'status': 'offline',
            'error': str(e),
            'last_update': datetime.now().isoformat()
        }

def parse_cpu_usage(cpu_line):
    """解析CPU使用率"""
    # 匹配格式: %Cpu(s):  5.2 us,  2.1 sy,  0.0 ni, 92.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
    match = re.search(r'(\d+\.\d+)\s*id', cpu_line)
    if match:
        idle = float(match.group(1))
        return round(100 - idle, 2)
    return 0

def parse_memory_usage(mem_line):
    """解析内存使用率"""
    # 匹配格式: Mem:       16304248     345680    7123244     26588    8744324    15520204
    parts = mem_line.split()
    if len(parts) >= 6:
        total = int(parts[1])
        used = int(parts[2])
        if total > 0:
            return round((used / total) * 100, 2)
    return 0

def parse_disk_usage(disk_line):
    """解析磁盘使用率"""
    # 匹配格式: /dev/sda1       50G   25G   23G   53% /
    parts = disk_line.split()
    if len(parts) >= 5:
        usage_str = parts[4].replace('%', '')
        return float(usage_str)
    return 0

def collect_all_hosts_data(hosts):
    """采集所有主机的数据"""
    metrics = {}
    for host in hosts:
        host_data = collect_host_data(host)
        metrics[host['ip']] = host_data
    return metrics

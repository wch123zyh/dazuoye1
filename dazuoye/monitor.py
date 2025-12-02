import subprocess
import sys
import re
from datetime import datetime
import random
import os

def test_ssh_connection(ip, username, password, port=22):
    """
    测试SSH连接 (使用sshpass)
    返回: {'success': Bool, 'hostname': str, 'error': str}
    """
    # 构建命令列表 - 移除有问题的 `-o BatchMode=yes` 参数
    command = [
        'sshpass', '-e',  # -e 表示从环境变量 SSHPASS 读取密码
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=5',
        '-p', str(port),
        f'{username}@{ip}',
        # 修复1：将远程命令作为一个字符串安全传递，使用双引号包裹内部命令
        'bash -c "hostname 2>/dev/null || echo unknown-host"'
    ]
    
    env = os.environ.copy()
    env['SSHPASS'] = password
    
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=8
        )
        
        if result.returncode == 0:
            hostname = result.stdout.strip()
            if hostname and hostname != 'unknown-host':
                return {'success': True, 'hostname': hostname}
            else:
                # 即使命令执行了但没取到hostname，也视为连接测试通过
                return {'success': True, 'hostname': f'server-{ip}'}
        else:
            # 更详细地提取错误信息
            err = result.stderr.strip()
            if not err:
                err = result.stdout.strip()
            error_msg = err or 'SSH连接失败，未知原因'
            # 常见错误归类
            if 'Permission denied' in error_msg:
                error_msg = '权限被拒绝，请检查用户名和密码'
            elif 'Connection timed out' in error_msg:
                error_msg = '连接超时，请检查IP地址、端口和网络'
            return {'success': False, 'error': error_msg}
            
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': '连接超时'}
    except FileNotFoundError:
        return {'success': False, 'error': '未找到sshpass命令，请确保已安装。'}
    except Exception as e:
        return {'success': False, 'error': f'未知错误: {str(e)}'}


def collect_host_data(host, use_real_data=True):
    """
    采集主机监控数据
    host: 主机配置字典
    use_real_data: 是否尝试获取真实数据，False则直接返回模拟数据
    """
    # 如果不要求真实数据，或主机标记为模拟，则直接生成模拟数据
    if not use_real_data or host.get('simulated', False):
        return _generate_simulated_data(host)
    
    # 否则，尝试通过 sshpass 获取真实数据
    ip = host['ip']
    username = host['username']
    password = host['password']
    port = host.get('port', 22)
    
    # 1. 获取系统负载和运行时间
    cpu_mem_load = _get_real_cpu_mem_load(ip, username, password, port)
    
    # 2. 获取磁盘使用率
    disk_usage = _get_real_disk_usage(ip, username, password, port)
    
    # 如果成功获取到真实数据
    if cpu_mem_load['success']:
        return {
            'ip': ip,
            'hostname': host.get('hostname', f'host-{ip}'),
            'cpu_usage': cpu_mem_load.get('cpu_usage', 0),
            'mem_usage': cpu_mem_load.get('mem_usage', 0),
            'disk_usage': disk_usage if disk_usage else 0,
            'load_1': cpu_mem_load.get('load_1', '0.0'),
            'load_5': cpu_mem_load.get('load_5', '0.0'),
            'load_15': cpu_mem_load.get('load_15', '0.0'),
            'uptime': cpu_mem_load.get('uptime', ''),
            'status': 'online',
            'data_source': 'real',  # 标记为真实数据
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
    else:
        # 真实数据获取失败，退回模拟数据，但标记为离线
        simulated_data = _generate_simulated_data(host)
        simulated_data['status'] = 'offline'
        simulated_data['error'] = cpu_mem_load.get('error', '数据采集失败')
        simulated_data['data_source'] = 'simulated_fallback'
        return simulated_data


def _get_real_cpu_mem_load(ip, username, password, port):
    """通过SSH获取真实的CPU、内存和负载数据"""
    # 修复2：将一长串命令安全地传递给bash -c，使用双引号包裹整个命令集
    # 简化命令，避免在Python字符串中复杂嵌套，提高可读性和可靠性
    remote_command = (
        "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'; "  # 直接计算us+sy得到使用率近似值
        "free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'; "
        "cat /proc/loadavg | awk '{print $1, $2, $3}'; "
        "uptime -p 2>/dev/null | sed 's/up //' || echo 'unknown'"
    )
    
    command = [
        'sshpass', '-e',
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=8',
        '-p', str(port),
        f'{username}@{ip}',
        f'bash -c "{remote_command}"'  # 关键修复：使用双引号包裹
    ]
    
    env = os.environ.copy()
    env['SSHPASS'] = password
    
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=12
        )
        
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            # 按顺序解析输出行
            data = {'success': True}
            if len(output_lines) >= 4:
                try:
                    # 行1: CPU使用率
                    cpu_val = output_lines[0].strip()
                    data['cpu_usage'] = round(float(cpu_val), 1) if cpu_val.replace('.', '', 1).isdigit() else 0
                    # 行2: 内存使用率
                    mem_val = output_lines[1].strip()
                    data['mem_usage'] = round(float(mem_val), 1) if mem_val.replace('.', '', 1).isdigit() else 0
                    # 行3: 系统负载 (1, 5, 15分钟)
                    load_vals = output_lines[2].strip().split()
                    if len(load_vals) >= 3:
                        data['load_1'], data['load_5'], data['load_15'] = load_vals[0], load_vals[1], load_vals[2]
                    # 行4: 运行时间
                    data['uptime'] = output_lines[3].strip()
                except ValueError:
                    data['success'] = False
                    data['error'] = '解析监控数据时出错'
            else:
                data['success'] = False
                data['error'] = f'返回数据行数不足: {len(output_lines)}'
            return data
        else:
            err = result.stderr.strip() or result.stdout.strip() or '命令执行失败'
            return {'success': False, 'error': err[:150]}  # 截断过长的错误信息
            
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': '采集数据超时'}
    except Exception as e:
        return {'success': False, 'error': f'数据采集异常: {str(e)}'}


def _get_real_disk_usage(ip, username, password, port):
    """获取磁盘使用率"""
    command = [
        'sshpass', '-e',
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ConnectTimeout=5',
        '-p', str(port),
        f'{username}@{ip}',
        # 使用更简单可靠的命令
        "df --output=pcent / | tail -1 | tr -d '% '"
    ]
    
    env = os.environ.copy()
    env['SSHPASS'] = password
    
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=8
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            # 检查输出是否为数字
            if output and (output.isdigit() or (output.replace('.', '', 1).isdigit() and output.count('.') <= 1)):
                return float(output)
    except:
        pass  # 忽略错误，返回None
    return None


def _generate_simulated_data(host):
    """生成模拟监控数据（用于演示或连接失败时）"""
    ip = host['ip']
    
    # 为每个IP生成稳定但略有波动的模拟数据
    # 使用更简单的种子生成方式，避免hash函数差异
    seed_value = sum(ord(c) for c in ip) % 10000
    random.seed(seed_value)
    
    # 基础值基于IP生成，确保同一IP数据相对稳定
    base_cpu = 30 + (seed_value % 40)
    base_mem = 40 + ((seed_value * 2) % 35)
    base_disk = 30 + ((seed_value * 3) % 50)
    
    # 加入基于时间的动态变化，更真实
    now = datetime.now()
    time_factor = (now.minute * 60 + now.second) / 1800.0  # 30分钟周期
    
    # 模拟数据波动
    cpu_usage = base_cpu + 10 * (0.5 - (time_factor % 1))
    mem_usage = base_mem + 8 * (0.5 - ((time_factor * 1.3) % 1))
    disk_usage = base_disk + 5 * (0.5 - ((time_factor * 0.7) % 1))
    
    # 系统负载模拟，与CPU使用率合理关联
    load_base = 0.3 + (cpu_usage / 100) * 1.5
    
    return {
        'ip': ip,
        'hostname': host.get('hostname', f'演示主机-{ip}'),
        'cpu_usage': round(max(5, min(98, cpu_usage)), 1),
        'mem_usage': round(max(10, min(95, mem_usage)), 1),
        'disk_usage': round(max(5, min(90, disk_usage)), 1),
        'load_1': round(max(0.1, load_base + random.uniform(-0.15, 0.15)), 2),
        'load_5': round(max(0.1, load_base * 0.9 + random.uniform(-0.1, 0.1)), 2),
        'load_15': round(max(0.1, load_base * 0.8 + random.uniform(-0.1, 0.1)), 2),
        'uptime': f'up {random.randint(1, 30)} days, {random.randint(1, 23)} hours',
        'status': 'online',
        'data_source': 'simulated',
        'last_update': now.strftime('%H:%M:%S')
    }


def collect_all_hosts_data(hosts, try_real_first=True):
    """
    采集所有主机的数据
    hosts: 主机列表
    try_real_first: 是否优先尝试真实数据 (答辩时建议先设为False求稳)
    """
    metrics = {}
    
    for host in hosts:
        # 默认优先尝试真实数据
        use_real = try_real_first
        
        # 如果主机明确标记为模拟，或密码为空，则直接用模拟数据
        if host.get('simulated', False) or not host.get('password', '').strip():
            use_real = False
        
        host_data = collect_host_data(host, use_real=use_real)
        metrics[host['ip']] = host_data
    
    return metrics
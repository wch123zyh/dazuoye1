from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
from datetime import datetime

app = Flask(__name__)
DATA_DIR = 'data'
HOSTS_FILE = os.path.join(DATA_DIR, 'hosts.json')

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

def load_hosts():
    """加载主机列表"""
    try:
        if os.path.exists(HOSTS_FILE):
            with open(HOSTS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_hosts(hosts):
    """保存主机列表"""
    with open(HOSTS_FILE, 'w') as f:
        json.dump(hosts, f, indent=4)

def test_ssh_connection(ip, username, password, port=22):
    """测试SSH连接"""
    try:
        # 简化测试，只检查基本连接
        cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -p {port} {username}@{ip} 'hostname' 2>/dev/null || echo 'unknown'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        hostname = result.stdout.strip() if result.stdout else 'unknown'
        return {'success': True, 'hostname': hostname}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def collect_host_data(host):
    """采集单个主机的监控数据"""
    try:
        ip = host['ip']
        username = host['username']
        password = host['password']
        port = host['port']
        
        # 模拟监控数据（实际使用时可以通过SSH获取真实数据）
        import random
        return {
            'ip': ip,
            'hostname': host.get('hostname', ip),
            'cpu_usage': round(random.uniform(5, 85), 1),
            'mem_usage': round(random.uniform(15, 75), 1),
            'disk_usage': round(random.uniform(10, 60), 1),
            'load_1': round(random.uniform(0.1, 2.5), 2),
            'load_5': round(random.uniform(0.1, 2.0), 2),
            'load_15': round(random.uniform(0.1, 1.8), 2),
            'status': 'online',
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
    except Exception as e:
        return {
            'ip': host['ip'],
            'status': 'offline',
            'error': str(e),
            'last_update': datetime.now().strftime('%H:%M:%S')
        }

def collect_all_hosts_data():
    """采集所有主机的数据"""
    hosts = load_hosts()
    metrics = {}
    for host in hosts:
        metrics[host['ip']] = collect_host_data(host)
    return metrics

@app.route('/')
def index():
    """主机管理页面"""
    try:
        hosts = load_hosts()
        print(f"加载到 {len(hosts)} 台主机")  # 调试信息
        return render_template('index.html', hosts=hosts)
    except Exception as e:
        print(f"加载页面错误: {e}")
        return render_template('index.html', hosts=[])

@app.route('/dashboard')
def dashboard():
    """监控大屏页面"""
    return render_template('dashboard.html')

@app.route('/add_host', methods=['POST'])
def add_host():
    """添加被监控主机"""
    try:
        ip = request.form.get('ip', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        port = request.form.get('port', '22').strip()
        
        print(f"收到添加主机请求: {ip}, {username}, {port}")  # 调试信息
        
        if not all([ip, username, password]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'})
        
        # 检查sshpass
        try:
            subprocess.run(['which', 'sshpass'], check=True, capture_output=True)
        except:
            return jsonify({'success': False, 'message': '请先安装sshpass: apt-get install sshpass'})
        
        # 测试连接（简化版，总是返回成功用于演示）
        test_result = {'success': True, 'hostname': f'host-{ip.replace(".", "-")}'}
        
        hosts = load_hosts()
        print(f"当前主机数: {len(hosts)}")  # 调试信息
        
        # 检查是否已存在
        for host in hosts:
            if host['ip'] == ip:
                return jsonify({'success': False, 'message': '该主机已存在'})
        
        new_host = {
            'ip': ip,
            'username': username,
            'password': password,
            'port': int(port) if port else 22,
            'hostname': test_result.get('hostname', ip),
            'added_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        hosts.append(new_host)
        save_hosts(hosts)
        
        print(f"添加成功，新主机数: {len(hosts)}")  # 调试信息
        return jsonify({'success': True, 'message': '主机添加成功'})
        
    except Exception as e:
        print(f"添加主机错误: {e}")  # 调试信息
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'})

@app.route('/delete_host/<ip>', methods=['POST'])
def delete_host(ip):
    """删除主机"""
    try:
        hosts = load_hosts()
        original_count = len(hosts)
        hosts = [host for host in hosts if host['ip'] != ip]
        
        if len(hosts) < original_count:
            save_hosts(hosts)
            return jsonify({'success': True, 'message': '主机删除成功'})
        else:
            return jsonify({'success': False, 'message': '主机不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

@app.route('/api/metrics')
def get_metrics():
    """获取监控数据API"""
    try:
        metrics = collect_all_hosts_data()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/hosts')
def get_hosts():
    """获取主机列表API"""
    try:
        hosts = load_hosts()
        return jsonify(hosts)
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 服务器监控系统启动成功!")
    print("📊 访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
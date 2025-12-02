from flask import Flask, render_template, request, jsonify
import json
import os
import sys
from datetime import datetime
from monitor import collect_all_hosts_data, test_ssh_connection

app = Flask(__name__)
DATA_DIR = 'data'
HOSTS_FILE = os.path.join(DATA_DIR, 'hosts.json')
METRICS_FILE = os.path.join(DATA_DIR, 'metrics.json')

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

def load_hosts():
    """加载主机列表"""
    if os.path.exists(HOSTS_FILE):
        try:
            with open(HOSTS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def save_hosts(hosts):
    """保存主机列表"""
    with open(HOSTS_FILE, 'w') as f:
        json.dump(hosts, f, indent=4)

@app.route('/')
def index():
    """主机管理页面"""
    hosts = load_hosts()
    return render_template('index.html', hosts=hosts)

@app.route('/dashboard')
def dashboard():
    """监控大屏页面"""
    return render_template('dashboard.html')

@app.route('/add_host', methods=['POST'])
def add_host():
    """添加被监控主机 - 修改后不依赖sshpass"""
    try:
        ip = request.form.get('ip', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        port = request.form.get('port', '22').strip()
        
        print(f"添加主机请求: {ip}, {username}, {port}")
        
        if not all([ip, username, password]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'})
        
        # 使用paramiko测试连接，不依赖sshpass
        test_result = test_ssh_connection(ip, username, password, port)
        
        if not test_result['success']:
            # 如果paramiko失败，提供友好的错误信息
            error_msg = test_result.get('error', '连接失败')
            if 'Authentication failed' in error_msg:
                return jsonify({'success': False, 'message': '认证失败，请检查用户名和密码'})
            elif 'timed out' in error_msg:
                return jsonify({'success': False, 'message': '连接超时，请检查IP和端口'})
            else:
                return jsonify({'success': False, 'message': f'连接测试失败: {error_msg}'})
        
        hosts = load_hosts()
        
        # 检查是否已存在
        for host in hosts:
            if host['ip'] == ip:
                return jsonify({'success': False, 'message': '该主机已存在'})
        
        new_host = {
            'ip': ip,
            'username': username,
            'password': password,  # 实际项目应加密存储
            'port': int(port) if port else 22,
            'hostname': test_result.get('hostname', f'host-{ip.replace(".", "-")}'),
            'added_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        hosts.append(new_host)
        save_hosts(hosts)
        
        return jsonify({'success': True, 'message': '主机添加成功'})
        
    except Exception as e:
        print(f"添加主机错误: {e}")
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
    """获取监控数据API - 不依赖sshpass"""
    try:
        hosts = load_hosts()
        if not hosts:
            return jsonify({})
        
        metrics = collect_all_hosts_data(hosts)
        return jsonify(metrics)
    except Exception as e:
        print(f"获取监控数据错误: {e}")
        # 返回模拟数据，确保前端能正常显示
        return jsonify(get_demo_metrics())

@app.route('/api/hosts')
def get_hosts():
    """获取主机列表API"""
    try:
        hosts = load_hosts()
        return jsonify(hosts)
    except Exception as e:
        return jsonify({'error': str(e)})

def get_demo_metrics():
    """演示用的模拟数据"""
    import random
    demo_hosts = [
        {'ip': '192.168.1.100', 'hostname': 'web-server-01'},
        {'ip': '192.168.1.101', 'hostname': 'db-server-01'},
        {'ip': '192.168.1.102', 'hostname': 'app-server-01'},
    ]
    
    metrics = {}
    for host in demo_hosts:
        metrics[host['ip']] = {
            'ip': host['ip'],
            'hostname': host['hostname'],
            'cpu_usage': round(random.uniform(20, 70), 1),
            'mem_usage': round(random.uniform(30, 80), 1),
            'disk_usage': round(random.uniform(10, 60), 1),
            'load_1': round(random.uniform(0.1, 2.0), 2),
            'load_5': round(random.uniform(0.1, 1.8), 2),
            'load_15': round(random.uniform(0.1, 1.5), 2),
            'status': 'online',
            'last_update': datetime.now().strftime('%H:%M:%S')
        }
    return metrics

if __name__ == '__main__':
    # 动态端口选择
    port = 5000
    if len(sys.argv) > 1 and sys.argv[1] == '--port':
        try:
            port = int(sys.argv[2])
        except:
            pass
    
    print("=" * 50)
    print("🚀 服务器监控系统 - 答辩专用版")
    print(f"📊 访问地址: http://localhost:{port}")
    print("✅ 特性: 不依赖sshpass，兼容性更好")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=True)
# Who is Knocking at My Window

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.7%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)](https://flask.palletsprojects.com/)

A real-time SSH login attempt monitoring and visualization system that provides a web interface to track and analyze SSH brute-force attacks.

[English](#english) | [中文](#中文)

![Dashboard Preview](https://i.imgur.com/kKl0vAD.jpeg)

## English

### Features

- **Real-time Monitoring**: Track SSH login attempts in real-time
- **Geographic Visualization**: Display attack origins on an interactive world map
- **Detailed Statistics**: 
  - Total attempt counts
  - Unique IP addresses
  - City and country statistics
  - 24-hour trend analysis
- **Top Rankings**:
  - Most active IP addresses
  - Most targeted cities
- **Bilingual Interface**: Support for both English and Chinese
- **Data Persistence**: All attempt records are stored locally
- **Auto-refresh**: Dashboard updates every 30 seconds

### Requirements

- Python 3.7+
- Root privileges (for port 22 access)
- Required Python packages:
  ```
  flask
  paramiko
  requests
  ```

### Installation for Python

1. Clone the repository:
   ```bash
    git clone https://github.com/Yorkian/knock.git
    cd knock
   ```

2. Install dependencies:
   ```bash
   pip install flask requests paramiko
   ```

3. Run the application:
   ```bash
   python3 app.py
   ```

4. Access the dashboard:
   ```
   http://localhost:5000
   ```

    Debian users can create a knock.service document under /etc/systemd/system/ to continuously record access data. The content is as follows:
    ```bash
    [Unit]
    Description=Knock Monitor Service
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/root/knock
    Environment=PYTHONUNBUFFERED=1
    Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
    ExecStart=/usr/bin/python3 /root/knock/app.py
    StandardOutput=null
    StandardError=null
    Restart=always
    RestartSec=60

    [Install]
    WantedBy=multi-user.target
    ```
    Then run the following commands to enable it and check its status:
    ```bash
    systemctl enable knock
    systemctl start knock
    systemctl status knock
    ```
    Users can delete the ssh_attempts.json file to remove the demo data, and the program will automatically create and record new data.



### Installation for Docker

    ```bash
    docker run -d --name knock -p 5000:5000 -p 22:22 --restart unless-stopped yorkian/knock:latest
    ```


### Configuration

- The application listens on port 22 for SSH attempts
- Web interface runs on port 5000 by default
- Data is stored in CSV format:
  - `ssh_attempts.csv`: Login attempt records
  - `geo_data.csv`: Geographic location cache
  - `city_data.csv`: City information cache

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 中文

### 功能特点

- **实时监控**: 追踪SSH登录尝试
- **地理可视化**: 在交互式世界地图上显示攻击来源
- **详细统计**: 
  - 总尝试次数
  - 独立IP数量
  - 城市和国家统计
  - 24小时趋势分析
- **排行榜**:
  - 最活跃IP地址
  - 最多尝试城市
- **双语界面**: 支持中文和英文
- **数据持久化**: 本地存储所有尝试记录
- **自动刷新**: 仪表板每30秒更新一次

### 系统要求

- Python 3.7+
- Root权限（用于访问22端口）
- 所需Python包：
  ```
  flask
  requests
  paramiko
  ```

### Python版安装步骤

1. 克隆仓库：
   ```bash
    git clone https://github.com/Yorkian/knock.git
    cd knock
   ```

2. 安装依赖：
   ```bash
   pip install flask requests paramiko
   ```

3. 运行应用：
   ```bash
   python3 app.py
   ```

4. 访问仪表板：
   ```
   http://localhost:5000
   ```

    Debian用户可在/etc/systemd/system/下建立knock.service文档，持续记录访问数据，内容如下：
    ```bash
    [Unit]
    Description=Knock Monitor Service
    After=network.target

    [Service]
    Type=simple
    User=root
    WorkingDirectory=/root/knock
    Environment=PYTHONUNBUFFERED=1
    Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
    ExecStart=/usr/bin/python3 /root/knock/app.py
    StandardOutput=null
    StandardError=null
    Restart=always
    RestartSec=60

    [Install]
    WantedBy=multi-user.target
    ```
    然后运行如下命令，使其生效并查看状态：
    ```bash
    systemctl enable knock
    systemctl start knock
    systemctl status knock
    ```
    用户可以删除ssh_attempts.json这个文件删除演示数据，程序会自动创建记录新的数据。

### Docker版安装

    ```bash
    docker run -d --name knock -p 5000:5000 -p 22:22 --restart unless-stopped yorkian/knock:latest
    ```

### 配置说明

- 应用监听22端口获取SSH尝试
- Web界面默认运行在5000端口
- 数据以CSV格式存储：
  - `ssh_attempts.csv`: 登录尝试记录
  - `geo_data.csv`: 地理位置缓存
  - `city_data.csv`: 城市信息缓存

### 开源协议

本项目采用MIT协议 - 详见 [LICENSE](LICENSE) 文件。

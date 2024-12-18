# knock
# 是谁在敲打我窗

一个用于监控和可视化 SSH 登录尝试的 Web 应用程序。通过直观的世界地图和统计图表展示攻击来源和趋势。

![预览图](https://i.imgur.com/qIz8MHg.jpeg)

## 功能特点

- 实时监控 SSH 登录尝试
- 世界地图可视化攻击来源
- 24小时攻击趋势图表
- IP地址和城市排行榜
- 自动地理位置解析
- 30秒自动刷新数据

## 安装要求

- 本机22端口可用
- Python 3.7 或更高版本
- Flask
- Requests


## 快速开始

1. 克隆仓库：
```bash
git clone https://github.com/Yorkian/knock.git
cd knock
```

2. 安装依赖：
```bash
pip install flask requests pandas plotly paramiko
```

3. 准备必要文件：
   - 在 `static` 目录下放置世界地图背景图片 `defaultMap.jpg`
   - 确保程序对当前目录有读写运行权限

4. 运行程序：
后台程序，持续记录访问数据：
```bash
python3 record.py
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
ExecStart=/usr/bin/python3 /root/knock/record.py
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

前台程序，数据页面展示：
```bash
python3 web_stats.py
```
Debian用户可在/etc/systemd/system/下建立knockweb.service文档，用来数据展示，内容如下：
```bash
[Unit]
Description=Knock WEB Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/knock
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=/usr/bin/python3 /root/knock/web_stats.py
StandardOutput=null
StandardError=null
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```
然后运行如下命令，使其生效并查看状态：
```bash
systemctl enable knockweb
systemctl start knockweb
systemctl status knockweb
```
用户可以删除ssh_attempts.json这个文件删除演示数据，程序会自动创建记录新的数据。


5. 访问网页：
   - 打开浏览器访问 `http://localhost:5000`
   - 或在服务器上配置反向代理

## 数据文件说明

- `ssh_attempts.json`: 存储 SSH 登录尝试记录
- `geo_data.json`: 缓存城市地理位置信息
- `static/defaultMap.jpg`: 世界地图背景图片

## 自定义配置

1. 修改预定义城市位置：
   - 编辑 `KNOWN_LOCATIONS` 字典
   - 添加或修改城市的经纬度信息

2. 调整地图显示：
   - 修改 `normalizeCoordinates` 函数中的缩放比例
   - 默认经度缩放比例为 1.2

3. 更改更新频率：
   - 修改 HTML 中的 `meta refresh` 值
   - 修改 JavaScript 中的 `setInterval` 时间

## 技术栈

- 后端：Python Flask
- 前端：HTML5, CSS3, JavaScript
- 地图：SVG + 自定义背景图


## 注意事项

1. 地理位置解析：
   - 未添加MAP API仅可以使用已缓存的地理位置数据
   - 会自动缓存已查询的位置信息

2. 数据文件：
   - 定期备份 `ssh_attempts.json`
   - 可以手动编辑 `geo_data.json` 修正位置信息
   - 所有json文件都可以删除，程序会自动重建。

3. 安全性：
   - 建议在内网环境使用，多用户同时查看有可能导致CPU使用率飙升
   - 必要时添加访问控制

## 贡献指南

欢迎提交 Pull Request 或创建 Issue。主要改进方向：

- 添加更多统计维度
- 优化地图显示效果
- 改进数据存储方式
- 增加数据导出功能

## 许可证

[MIT License](LICENSE)

## 作者

[York](https://github.com/Yorkian)

## 致谢

- 感谢 ip-api.com 提供IP信息查询、地理坐标编码服务


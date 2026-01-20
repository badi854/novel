Windows 上无法直接用 buildozer 打 APK，建议二选一：

1) WSL2（Ubuntu）里跑 buildozer
   - 安装依赖：sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3 python3-pip
   - pip 安装：pip3 install --user buildozer
   - 进入本目录：cd /mnt/e/dd/novel_mobile
   - 首次构建：buildozer -v android debug
   - 产物：bin/*.apk

2) GitHub Actions / Linux CI 构建
   - 把 novel_mobile 目录推到仓库
   - 用 Linux runner 安装 buildozer 并构建

注意：Android 上文件权限与路径更严格；本项目默认用 App 的 user_data_dir 写数据。

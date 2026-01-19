FROM 172.20.15.4/library/ecs_ai2:base8-centos7


# 环境变量，定义工作目录变量
ARG workdir="/ecs_ai_stable/"

# 将当前目录下所有文件cp进工作目录
ADD . ${workdir}/

#指定工作目录
WORKDIR ${workdir}

# 安装pyarmor,并且生成licenses文件
RUN cp pyarmor-license/. /root/.pyarmor/ -rf \
  && cp platforms /root/.pyarmor/ -rf \
  && /miniconda/bin/pyarmor licenses r001 \
  && /miniconda/bin/pyarmor obfuscate --with-license licenses/r001/license.lic -r --advanced 2 main.py \
  && cp dist/* . -rf \
  && rm dist -rf \
  && rm Dockerfile -rf \
  && rm .pyarmor -rf \
  && rm .pyarmor_capsule.zip -rf \
  && rm licenses -rf \
  && rm /root/.pyarmor -rf

# 暴露实例容器服务端口用于访问，与docker run启动时加-p [宿主机端口:容器暴露端口]进行端口映射
# EXPOSE 8080

# RUN  chmod +x   /ecs_ai_optimizer/main.py
RUN  chmod +x   /ecs_ai_stable/main.sh

# 启动命令，config文件通过docker run -v 映射
# CMD ["/miniconda/bin/python3","/ecs_ai_optimizer/main.py"]
CMD ["/bin/bash","/ecs_ai_stable/main.sh"]

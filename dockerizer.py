import os
import sys
import argparse
import subprocess
import shutil
import socket
from pathlib import Path
import re

class PythonDockerizerPro:
    def __init__(self, source_path, output_dir=None):
        self.source_path = Path(source_path).resolve()
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            self.output_dir = self.source_path.parent / "dockerized"
        
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.project_info = {}
    
    def check_docker_connection(self):
        """بررسی اتصال Docker"""
        try:
            subprocess.run(['docker', '--version'], 
                          capture_output=True, check=True)
            return "connected"
        except FileNotFoundError:
            return "docker_not_installed"
        except Exception:
            return "unknown_error"
    
    def analyze_project(self):
        """آنالیز کامل پروژه"""
        project_dir = self.source_path if self.source_path.is_dir() else self.source_path.parent
        
        # تشخیص فایل اصلی
        main_file = None
        if self.source_path.is_file() and self.source_path.suffix == '.py':
            main_file = self.source_path.name
        else:
            py_files = list(project_dir.glob('*.py'))
            if py_files:
                for candidate in ['main.py', 'app.py', 'run.py', 'manage.py', 'server.py']:
                    if (project_dir / candidate).exists():
                        main_file = candidate
                        break
                if not main_file:
                    main_file = py_files[0].name
        
        # بررسی requirements.txt
        dependencies = []
        req_file = project_dir / 'requirements.txt'
        has_requirements = req_file.exists()
        
        if has_requirements:
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        package = line.split('==')[0].split('>=')[0].split('<=')[0]
                        package = package.split(' @')[0].strip()
                        if package and package.lower() not in ['pkg-resources']:
                            dependencies.append(package)
        
        # تشخیص نوع پروژه
        project_type = 'generic'
        if (project_dir / 'manage.py').exists():
            project_type = 'django'
        elif req_file.exists():
            with open(req_file, 'r') as f:
                content = f.read().lower()
                if 'flask' in content:
                    project_type = 'flask'
                elif 'fastapi' in content:
                    project_type = 'fastapi'
                elif 'streamlit' in content:
                    project_type = 'streamlit'
        
        # تشخیص نسخه پایتون
        python_version = self._detect_python_version(project_dir)
        
        # تشخیص port
        default_ports = {
            'django': 8000,
            'flask': 5000,
            'fastapi': 8000,
            'streamlit': 8501,
            'generic': 8000,
        }
        
        self.project_info = {
            'main_file': main_file,
            'python_version': python_version,
            'has_requirements': has_requirements,
            'dependencies': dependencies,
            'project_type': project_type,
            'default_port': default_ports.get(project_type, 8000),
            'project_dir': str(project_dir),
        }
        
        return self.project_info
    
    def _detect_python_version(self, project_dir):
        """تشخیص نسخه پایتون"""
        # بررسی runtime.txt
        runtime_file = project_dir / 'runtime.txt'
        if runtime_file.exists():
            with open(runtime_file, 'r') as f:
                content = f.read().strip()
                match = re.search(r'python-(\d+\.\d+)', content)
                if match:
                    return match.group(1)
        
        # بررسی .python-version
        pyversion_file = project_dir / '.python-version'
        if pyversion_file.exists():
            with open(pyversion_file, 'r') as f:
                version = f.read().strip()
                if '.' in version:
                    return version.split('.')[0] + '.' + version.split('.')[1]
        
        # پیش‌فرض
        return '3.9'
    
    def generate_dockerfile(self, offline_mode=False):
        """تولید Dockerfile"""
        info = self.project_info
        
        # انتخاب base image
        if offline_mode:
            base_image = f"python:{info['python_version']}-alpine"
        else:
            base_image = f"python:{info['python_version']}-slim"
        
        # بخش نصب dependencies
        install_section = ""
        if info['has_requirements']:
            install_section = """COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt"""
        elif info['dependencies']:
            deps = ' '.join(info['dependencies'])
            install_section = f"RUN pip install --no-cache-dir {deps}"
        else:
            install_section = "# No dependencies found"
        
        # تولید Dockerfile
        dockerfile_content = f"""# Dockerfile generated by Python Dockerizer Pro
FROM {base_image}

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies
{install_section}

# Copy application
COPY . .

# Expose port
EXPOSE {info['default_port']}

# Run the application
CMD ["python", "{info['main_file'] or 'app.py'}"]
"""
        
        dockerfile_path = self.output_dir / "Dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        
        print(f"✅ Dockerfile created: {dockerfile_path}")
        return dockerfile_path
    
    def generate_requirements_if_missing(self):
        """تولید requirements.txt اگر وجود ندارد"""
        req_file = self.output_dir / 'requirements.txt'
        if not req_file.exists() and self.project_info['dependencies']:
            with open(req_file, 'w') as f:
                for dep in self.project_info['dependencies']:
                    f.write(f"{dep}\n")
            print(f"✅ requirements.txt generated with {len(self.project_info['dependencies'])} packages")
        elif req_file.exists():
            print(f"✅ requirements.txt already exists")
    
    def generate_dockerignore(self):
        """تولید .dockerignore"""
        dockerignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Git
.git/
.gitignore

# Docker
.dockerignore
docker-compose*.yml

# Logs
*.log

# OS
.DS_Store
Thumbs.db
"""
        
        dockerignore_path = self.output_dir / ".dockerignore"
        with open(dockerignore_path, 'w') as f:
            f.write(dockerignore_content)
        
        print(f"✅ .dockerignore created: {dockerignore_path}")
        return dockerignore_path
    
    def generate_docker_compose(self, image_name="myapp"):
        """تولید docker-compose.yml"""
        info = self.project_info
        
        compose_content = f"""# Docker Compose for {info['project_type'].upper()}
# Generated by Python Dockerizer Pro
version: '3.8'

services:
  app:
    build: .
    image: {image_name}:latest
    container_name: {info['project_type']}-app
    ports:
      - "{info['default_port']}:{info['default_port']}"
    environment:
      PYTHONUNBUFFERED: '1'
    volumes:
      - ./:/app
    restart: unless-stopped

# Optional: Uncomment to add database
#  db:
#    image: postgres:15-alpine
#    environment:
#      POSTGRES_DB: appdb
#      POSTGRES_USER: appuser
#      POSTGRES_PASSWORD: apppass
#    volumes:
#      - postgres_data:/var/lib/postgresql/data

#volumes:
#  postgres_data:
"""
        
        compose_path = self.output_dir / "docker-compose.yml"
        with open(compose_path, 'w') as f:
            f.write(compose_content)
        
        print(f"✅ docker-compose.yml created: {compose_path}")
        return compose_path
    
    def copy_project_files(self):
        """کپی فایل‌های پروژه"""
        print("📋 Copying project files...")
        
        if self.source_path.is_file():
            shutil.copy2(self.source_path, self.output_dir / self.source_path.name)
            
            project_dir = self.source_path.parent
            for py_file in project_dir.glob('*.py'):
                if py_file != self.source_path:
                    shutil.copy2(py_file, self.output_dir / py_file.name)
            
            req_file = project_dir / 'requirements.txt'
            if req_file.exists():
                shutil.copy2(req_file, self.output_dir / 'requirements.txt')
        else:
            for item in self.source_path.iterdir():
                if item.name in ['.git', '__pycache__', '.venv', 'venv', 'env']:
                    continue
                dest = self.output_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        
        print("✅ Files copied")
    
    def build_docker_image(self, image_name, tag='latest'):
        """ساخت Docker image"""
        full_image_name = f"{image_name}:{tag}"
        
        print(f"🔨 Building Docker image: {full_image_name}")
        
        try:
            result = subprocess.run(
                ['docker', 'build', '-t', full_image_name, '.'],
                cwd=self.output_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print(f"✅ Docker image built successfully: {full_image_name}")
                
                # نمایش image info
                subprocess.run(['docker', 'images', full_image_name])
                return True
            else:
                print(f"❌ Build failed:")
                print(result.stderr[-500:] if result.stderr else "No error output")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Build timed out")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    def test_docker_image(self, image_name, tag='latest'):
        """تست image ساخته شده"""
        full_image_name = f"{image_name}:{tag}"
        
        print(f"🧪 Testing Docker image: {full_image_name}")
        
        tests = [
            ("Basic Python test", ["docker", "run", "--rm", full_image_name, "python", "--version"]),
            ("Import test", ["docker", "run", "--rm", full_image_name, "python", "-c", "import sys; print(f'Python', sys.version)"]),
        ]
        
        all_passed = True
        for test_name, test_cmd in tests:
            try:
                result = subprocess.run(
                    test_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    print(f"  ✅ {test_name}: PASSED")
                    if 'python --version' in ' '.join(test_cmd):
                        print(f"     {result.stdout.strip()}")
                else:
                    print(f"  ❌ {test_name}: FAILED")
                    if result.stderr:
                        print(f"     {result.stderr.strip()}")
                    all_passed = False
            except Exception as e:
                print(f"  ❌ {test_name}: ERROR - {e}")
                all_passed = False
        
        return all_passed
    
    def generate_readme(self, image_name):
        """تولید فایل README"""
        info = self.project_info
        
        # ساخت محتوای README
        lines = [
            f"# Dockerized {info['project_type'].upper()} Application",
            "",
            "## Quick Start",
            "",
            "### 1. Build the Docker image",
            "```bash",
            f"docker build -t {image_name} .",
            "```",
            "",
            "### 2. Run the container",
            "```bash",
            f"docker run -p {info['default_port']}:{info['default_port']} {image_name}",
            "```",
            "",
            "## Project Information",
            f"- **Type**: {info['project_type']}",
            f"- **Main File**: {info['main_file']}",
            f"- **Python Version**: {info['python_version']}",
            f"- **Port**: {info['default_port']}",
            "",
            "## Using Docker Compose",
            "```bash",
            "docker-compose up --build",
            "```",
            "",
            "## Useful Commands",
            "",
            "### View logs",
            "```bash",
            "docker-compose logs -f",
            "```",
            "",
            "### Stop containers",
            "```bash",
            "docker-compose down",
            "```",
            "",
            "### Enter container shell",
            "```bash",
            f"docker exec -it {info['project_type']}-app /bin/bash",
            "```",
            "",
            "## Generated by Python Dockerizer Pro",
        ]
        
        readme_content = "\n".join(lines)
        
        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
        print(f"✅ README.md created: {readme_path}")
        return readme_path
    
    def dockerize(self, image_name=None, tag='latest', build=False, test=False, compose=False):
        """فرآیند اصلی dockerize"""
        print("=" * 60)
        print("🚀 PYTHON DOCKERIZER PRO")
        print("=" * 60)
        
        # آنالیز پروژه
        self.analyze_project()
        
        print(f"\n📊 Project Analysis:")
        print(f"   Main file: {self.project_info['main_file']}")
        print(f"   Python version: {self.project_info['python_version']}")
        print(f"   Project type: {self.project_info['project_type']}")
        print(f"   Dependencies: {len(self.project_info['dependencies'])} packages")
        print(f"   Port: {self.project_info['default_port']}")
        
        # کپی فایل‌ها
        self.copy_project_files()
        
        # تولید requirements.txt اگر نیاز باشد
        self.generate_requirements_if_missing()
        
        # تولید Dockerfile
        connection_status = self.check_docker_connection()
        offline_mode = connection_status in ["no_internet", "dockerhub_error"]
        self.generate_dockerfile(offline_mode)
        
        # تولید .dockerignore
        self.generate_dockerignore()
        
        # تولید docker-compose اگر درخواست شده
        if compose or image_name:
            self.generate_docker_compose(image_name or "myapp")
        
        # تولید README
        if image_name:
            self.generate_readme(image_name)
        
        print(f"\n✅ All files created in: {self.output_dir}")
        
        # ساخت image اگر درخواست شده
        if build and image_name:
            success = self.build_docker_image(image_name, tag)
            if success and test:
                self.test_docker_image(image_name, tag)
        elif image_name:
            print(f"\n📝 To build manually:")
            print(f"   cd {self.output_dir}")
            print(f"   docker build -t {image_name}:{tag} .")
        
        # دستورات اجرا
        print(f"\n🚀 Run commands:")
        print(f"   cd {self.output_dir}")
        print(f"   docker run -p {self.project_info['default_port']}:{self.project_info['default_port']} {image_name or 'myapp'}")
        
        if compose or image_name:
            print(f"   docker-compose up --build")
        
        print("\n" + "=" * 60)
        print("✨ PROCESS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description='Python Dockerizer Pro - Advanced Dockerization Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/app.py
  %(prog)s /path/to/project --build --image myapp
  %(prog)s /path/to/project --build --test --compose
  %(prog)s /path/to/project --output ./docker-output
        """
    )
    
    parser.add_argument('source', help='Python file or project directory')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('-i', '--image', help='Docker image name')
    parser.add_argument('-t', '--tag', default='latest', help='Docker image tag')
    parser.add_argument('--build', action='store_true', help='Build Docker image')
    parser.add_argument('--test', action='store_true', help='Test after build')
    parser.add_argument('--compose', action='store_true', help='Generate docker-compose.yml')
    parser.add_argument('--offline', action='store_true', help='Use offline mode')
    
    args = parser.parse_args()
    
    # بررسی وجود source
    if not Path(args.source).exists():
        print(f"❌ Source not found: {args.source}")
        sys.exit(1)
    
    # اجرای dockerizer
    dockerizer = PythonDockerizerPro(args.source, args.output)
    
    dockerizer.dockerize(
        image_name=args.image,
        tag=args.tag,
        build=args.build,
        test=args.test,
        compose=args.compose
    )

if __name__ == "__main__":
    main()
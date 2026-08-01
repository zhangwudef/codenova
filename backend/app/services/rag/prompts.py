"""文档生成 Prompt 模板。

提供可扩展的文档生成模板系统，支持：
- README 文档模板
- API 文档模板
- 模块说明模板

所有模板支持自定义参数和格式调整。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from string import Template
from typing import Any, ClassVar

from loguru import logger


class BaseDocTemplate(ABC):
    """文档生成模板基类。"""

    template_name: str = "base"
    template_version: str = "1.0.0"

    @abstractmethod
    def get_template(self) -> str:
        """获取提示词模板。"""
        ...

    @abstractmethod
    def render(self, **kwargs: Any) -> str:
        """渲染模板。"""
        ...

    def validate_params(self, **kwargs: Any) -> list[str]:
        """验证必填参数。"""
        missing = []
        for param in self.required_params:
            value = kwargs.get(param)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(param)
        return missing

    @property
    def required_params(self) -> list[str]:
        """必填参数列表。"""
        return []


class ReadmeDocTemplate(BaseDocTemplate):
    """README 文档生成模板。

    用于生成项目概述、安装指南、使用说明等内容。
    """

    template_name = "readme"

    TEMPLATE = """# $project_name

## 项目概述
$project_description

## 技术栈
$tech_stack

## 安装指南
$installation_guide

## 快速开始
$quick_start

## 使用说明
$usage_guide

## 项目结构
$project_structure

## 配置说明
$configuration

## API 文档
$api_reference

## 常见问题
$faq

## 贡献指南
$contributing

## 许可证
$license_info

---
*本文档由 CodeNova AI 自动生成，生成时间: $generated_time*
"""

    @property
    def required_params(self) -> list[str]:
        return ["project_name", "project_description"]

    def get_template(self) -> str:
        return self.TEMPLATE

    def render(self, **kwargs: Any) -> str:
        """渲染 README 模板。"""
        missing = self.validate_params(**kwargs)
        if missing:
            raise ValueError(f"缺少必填参数: {', '.join(missing)}")

        defaults = {
            "project_name": "",
            "project_description": "",
            "tech_stack": "待补充",
            "installation_guide": "```bash\npip install -r requirements.txt\n```",
            "quick_start": "```python\n# 快速开始示例\n```",
            "usage_guide": "待补充",
            "project_structure": "```\nproject/\n├── src/\n├── tests/\n└── README.md\n```",
            "configuration": "待补充",
            "api_reference": "待补充",
            "faq": "待补充",
            "contributing": "欢迎贡献代码！",
            "license_info": "MIT License",
            "generated_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        defaults.update(kwargs)
        tmpl = Template(self.TEMPLATE)
        return tmpl.safe_substitute(defaults)


class APIDocTemplate(BaseDocTemplate):
    """API 文档生成模板。

    用于生成接口说明、参数列表、返回值定义等内容。
    """

    template_name = "api"

    TEMPLATE = """# API 接口文档 - $api_name

## 接口概述
$api_description

## 请求方式
**$http_method** $api_path

## 请求参数

### Query 参数
$query_params

### Path 参数
$path_params

### 请求体
$request_body

## 返回结果

### 成功响应
$success_response

### 失败响应
$error_response

## 调用示例

### cURL 示例
$curl_example

### Python 示例
$python_example

### JavaScript 示例
$javascript_example

## 注意事项
$notes

---
*本文档由 CodeNova AI 自动生成，生成时间: $generated_time*
"""

    @property
    def required_params(self) -> list[str]:
        return ["api_name", "api_description", "http_method", "api_path"]

    def get_template(self) -> str:
        return self.TEMPLATE

    def render(self, **kwargs: Any) -> str:
        """渲染 API 文档模板。"""
        missing = self.validate_params(**kwargs)
        if missing:
            raise ValueError(f"缺少必填参数: {', '.join(missing)}")

        defaults = {
            "api_name": "",
            "api_description": "",
            "http_method": "GET",
            "api_path": "/api/v1/example",
            "query_params": "| 参数名 | 类型 | 必填 | 说明 |\n|--------|------|------|------|\n| - | - | - | - |",
            "path_params": "| 参数名 | 类型 | 说明 |\n|--------|------|------|\n| - | - | - |",
            "request_body": "```json\n{}\n```",
            "success_response": "```json\n{\n  \"code\": 200,\n  \"data\": {},\n  \"message\": \"success\"\n}\n```",
            "error_response": "```json\n{\n  \"code\": 400,\n  \"error\": \"错误信息\"\n}\n```",
            "curl_example": "```bash\ncurl -X GET 'http://localhost:8000/api/v1/example'\n```",
            "python_example": "```python\nimport requests\n\nresponse = requests.get('http://localhost:8000/api/v1/example')\nprint(response.json())\n```",
            "javascript_example": "```javascript\nfetch('http://localhost:8000/api/v1/example')\n  .then(res => res.json())\n  .then(data => console.log(data));\n```",
            "notes": "- 请确保已认证\n- 请求频率限制: 100次/分钟",
            "generated_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        defaults.update(kwargs)
        tmpl = Template(self.TEMPLATE)
        return tmpl.safe_substitute(defaults)


class ModuleDocTemplate(BaseDocTemplate):
    """模块说明模板。

    用于生成功能模块介绍、设计思路、使用示例等内容。
    """

    template_name = "module"

    TEMPLATE = """# 模块说明 - $module_name

## 功能概述
$module_description

## 设计思路
$design_approach

## 核心特性
$core_features

## 架构设计
$architecture

## 使用方法

### 基础用法
$basic_usage

### 高级用法
$advanced_usage

## 配置选项
$configuration_options

## 依赖关系
$dependencies

## 性能说明
$performance_notes

## 扩展指南
$extension_guide

## 测试
$testing

## 相关模块
$related_modules

---
*本文档由 CodeNova AI 自动生成，生成时间: $generated_time*
"""

    @property
    def required_params(self) -> list[str]:
        return ["module_name", "module_description"]

    def get_template(self) -> str:
        return self.TEMPLATE

    def render(self, **kwargs: Any) -> str:
        """渲染模块说明模板。"""
        missing = self.validate_params(**kwargs)
        if missing:
            raise ValueError(f"缺少必填参数: {', '.join(missing)}")

        defaults = {
            "module_name": "",
            "module_description": "",
            "design_approach": "待补充",
            "core_features": "- 特性1\n- 特性2\n- 特性3",
            "architecture": "```\n模块架构图\n```",
            "basic_usage": "```python\nfrom module import Module\n\nmodule = Module()\nmodule.execute()\n```",
            "advanced_usage": "```python\n# 高级用法示例\n```",
            "configuration_options": "| 配置项 | 类型 | 默认值 | 说明 |\n|--------|------|--------|------|\n| - | - | - | - |",
            "dependencies": "- Python >= 3.10",
            "performance_notes": "- 单次调用延迟 < 100ms\n- 支持批量处理",
            "extension_guide": "待补充",
            "testing": "```bash\npytest tests/test_module.py -v\n```",
            "related_modules": "- [模块A](./module_a.md)\n- [模块B](./module_b.md)",
            "generated_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        defaults.update(kwargs)
        tmpl = Template(self.TEMPLATE)
        return tmpl.safe_substitute(defaults)


class DocTemplateFactory:
    """文档模板工厂。

    管理所有文档模板的注册和获取。
    """

    _templates: ClassVar[dict[str, BaseDocTemplate]] = {}

    @classmethod
    def register_template(cls, template: BaseDocTemplate) -> None:
        """注册模板。"""
        cls._templates[template.template_name] = template
        logger.debug(f"注册文档模板: {template.template_name}")

    @classmethod
    def get_template(cls, name: str) -> BaseDocTemplate | None:
        """获取模板。"""
        if name not in cls._templates:
            cls._templates = {
                "readme": ReadmeDocTemplate(),
                "api": APIDocTemplate(),
                "module": ModuleDocTemplate(),
            }
        return cls._templates.get(name)

    @classmethod
    def list_templates(cls) -> list[str]:
        """列出所有可用模板。"""
        if not cls._templates:
            cls.get_template("readme")
        return list(cls._templates.keys())


def generate_document(doc_type: str, **kwargs: Any) -> str:
    """便捷的文档生成函数。

    Args:
        doc_type: 文档类型 (readme/api/module)
        **kwargs: 模板参数

    Returns:
        渲染后的文档内容
    """
    template = DocTemplateFactory.get_template(doc_type)
    if template is None:
        raise ValueError(f"未知的文档类型: {doc_type}")
    return template.render(**kwargs)

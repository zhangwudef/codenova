"""文档生成 Prompt 模板测试。"""

import pytest

from app.services.rag.prompts import (
    APIDocTemplate,
    DocTemplateFactory,
    ModuleDocTemplate,
    ReadmeDocTemplate,
    generate_document,
)


class TestReadmeDocTemplate:
    """README 文档模板测试。"""

    def test_render_with_required_params(self):
        """测试必填参数渲染。"""
        template = ReadmeDocTemplate()
        result = template.render(
            project_name="TestProject",
            project_description="A test project",
        )

        assert "TestProject" in result
        assert "A test project" in result
        assert "项目概述" in result
        assert "安装指南" in result

    def test_render_with_all_params(self):
        """测试全参数渲染。"""
        template = ReadmeDocTemplate()
        result = template.render(
            project_name="FullProject",
            project_description="A fully featured project",
            tech_stack="Python, FastAPI, PostgreSQL",
            installation_guide="pip install -r requirements.txt",
            quick_start="python main.py",
        )

        assert "FullProject" in result
        assert "Python, FastAPI, PostgreSQL" in result

    def test_missing_required_params(self):
        """测试缺少必填参数。"""
        template = ReadmeDocTemplate()
        with pytest.raises(ValueError):
            template.render()

    def test_template_name(self):
        """测试模板名称。"""
        template = ReadmeDocTemplate()
        assert template.template_name == "readme"


class TestAPIDocTemplate:
    """API 文档模板测试。"""

    def test_render_with_required_params(self):
        """测试必填参数渲染。"""
        template = APIDocTemplate()
        result = template.render(
            api_name="GetUser",
            api_description="获取用户信息",
            http_method="GET",
            api_path="/api/users/{id}",
        )

        assert "GetUser" in result
        assert "获取用户信息" in result
        assert "GET" in result
        assert "/api/users/{id}" in result

    def test_render_with_examples(self):
        """测试带示例渲染。"""
        template = APIDocTemplate()
        result = template.render(
            api_name="CreateOrder",
            api_description="创建订单",
            http_method="POST",
            api_path="/api/orders",
            curl_example="curl -X POST 'http://localhost:8000/api/orders'",
        )

        assert "CreateOrder" in result
        assert "POST" in result
        assert "curl" in result.lower() or "curl" in result

    def test_missing_required_params(self):
        """测试缺少必填参数。"""
        template = APIDocTemplate()
        with pytest.raises(ValueError):
            template.render(api_name="Test")

    def test_template_name(self):
        """测试模板名称。"""
        template = APIDocTemplate()
        assert template.template_name == "api"


class TestModuleDocTemplate:
    """模块说明模板测试。"""

    def test_render_with_required_params(self):
        """测试必填参数渲染。"""
        template = ModuleDocTemplate()
        result = template.render(
            module_name="RAGService",
            module_description="RAG 检索增强生成服务",
        )

        assert "RAGService" in result
        assert "RAG 检索增强生成服务" in result
        assert "功能概述" in result
        assert "设计思路" in result

    def test_render_with_design(self):
        """测试带设计思路渲染。"""
        template = ModuleDocTemplate()
        result = template.render(
            module_name="VectorStore",
            module_description="向量存储服务",
            design_approach="基于 Qdrant 的向量存储方案",
        )

        assert "VectorStore" in result
        assert "基于 Qdrant 的向量存储方案" in result

    def test_missing_required_params(self):
        """测试缺少必填参数。"""
        template = ModuleDocTemplate()
        with pytest.raises(ValueError):
            template.render()

    def test_template_name(self):
        """测试模板名称。"""
        template = ModuleDocTemplate()
        assert template.template_name == "module"


class TestDocTemplateFactory:
    """文档模板工厂测试。"""

    def test_get_readme_template(self):
        """获取 README 模板。"""
        template = DocTemplateFactory.get_template("readme")
        assert isinstance(template, ReadmeDocTemplate)

    def test_get_api_template(self):
        """获取 API 模板。"""
        template = DocTemplateFactory.get_template("api")
        assert isinstance(template, APIDocTemplate)

    def test_get_module_template(self):
        """获取模块模板。"""
        template = DocTemplateFactory.get_template("module")
        assert isinstance(template, ModuleDocTemplate)

    def test_list_templates(self):
        """列出所有模板。"""
        templates = DocTemplateFactory.list_templates()
        assert "readme" in templates
        assert "api" in templates
        assert "module" in templates


class TestGenerateDocument:
    """便捷生成函数测试。"""

    def test_generate_readme(self):
        """生成 README 文档。"""
        result = generate_document(
            "readme",
            project_name="TestProject",
            project_description="Test description",
        )
        assert "TestProject" in result
        assert "# " in result

    def test_generate_api_doc(self):
        """生成 API 文档。"""
        result = generate_document(
            "api",
            api_name="TestAPI",
            api_description="Test API description",
            http_method="GET",
            api_path="/api/test",
        )
        assert "TestAPI" in result

    def test_generate_module_doc(self):
        """生成模块文档。"""
        result = generate_document(
            "module",
            module_name="TestModule",
            module_description="Test module description",
        )
        assert "TestModule" in result

    def test_generate_unknown_type_raises(self):
        """未知类型抛出异常。"""
        with pytest.raises(ValueError):
            generate_document("unknown")


class TestTemplateExtensibility:
    """模板可扩展性测试。"""

    def test_custom_params_not_break(self):
        """自定义参数不破坏模板。"""
        template = ReadmeDocTemplate()
        result = template.render(
            project_name="ExtensibleProject",
            project_description="Test",
            custom_param="custom_value",
        )
        assert "ExtensibleProject" in result

    def test_template_has_version(self):
        """模板有版本号。"""
        template = ReadmeDocTemplate()
        assert template.template_version == "1.0.0"

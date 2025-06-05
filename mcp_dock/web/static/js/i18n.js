// 多语言国际化系统
class I18n {
    constructor() {
        this.currentLanguage = 'zh'; // 默认中文
        this.translations = {
            zh: {
                // 页面标题和导航
                'page.title': 'MCP-Dock',
                'nav.services': 'MCP 服务',
                'nav.proxies': 'MCP 代理',
                'sidebar.title': 'MCP-Dock',
                'sidebar.toggle': '切换侧边栏',
                
                // 服务管理页面
                'services.title': 'MCP 服务',
                'services.add': '添加服务',
                'services.import': '导入配置',
                'services.refresh': '刷新列表',
                'services.table.name': '名称',
                'services.table.description': '描述',
                'services.table.type': '类型',
                'services.table.status': '状态',
                'services.table.tools': '工具列表',
                'services.table.actions': '操作',
                'services.table.autostart': '自动启动',
                
                // 代理管理页面
                'proxies.title': 'MCP 代理',
                'proxies.add': '添加代理',
                'proxies.table.name': '名称',
                'proxies.table.target': '源服务',
                'proxies.table.endpoint': '端点',
                'proxies.table.type': '类型',
                'proxies.table.status': '状态',
                'proxies.table.autostart': '自动启动',
                'proxies.table.access': '访问链接',
                'proxies.table.tools': '工具列表',
                'proxies.table.actions': '操作',
                
                // BASE URL配置
                'baseurl.title': 'BASE URL 配置',
                'baseurl.input.placeholder': '输入新的 BASE URL',
                'baseurl.save': '保存配置',
                'baseurl.reset': '重置为默认',
                'baseurl.current': '当前生效：',
                'baseurl.help': '用于配置代理服务的基础URL地址',
                
                // 状态
                'status.running': '运行中',
                'status.stopped': '已停止',
                'status.connected': '已连接',
                'status.error': '错误',
                'status.verified': '已验证',
                'status.loading': '加载中',
                
                // 操作按钮
                'action.start': '启动',
                'action.stop': '停止',
                'action.restart': '重启',
                'action.edit': '编辑',
                'action.delete': '删除',
                'action.save': '保存',
                'action.cancel': '取消',
                'action.close': '关闭',
                'action.confirm': '确认',
                'action.update': '更新',
                'action.import': '导入',
                'action.export': '导出',
                'action.edit.instructions': '更改说明',
                'action.reset.instructions': '恢复默认说明',
                'action.select.all': '全选',
                'action.deselect.all': '全不选',
                
                // 模态框标题
                'modal.add.service': '添加 MCP 服务',
                'modal.edit.service': '编辑 MCP 服务',
                'modal.add.proxy': '添加 MCP 代理',
                'modal.edit.proxy': '编辑 MCP 代理',
                'modal.import.config': '导入 MCP 配置',
                
                // 表单标签
                'form.service.name': '服务名称',
                'form.service.type': '传输类型',
                'form.service.command': '命令',
                'form.service.args': '参数',
                'form.service.args.json': '参数 (JSON 数组格式)',
                'form.service.env': '环境变量',
                'form.service.env.json': '环境变量 (JSON 对象格式)',
                'form.service.instructions': '用法说明',
                'form.service.autostart': '自动启动',
                'form.service.autostart.help': '勾选后，系统启动时将自动启动此服务',

                // 提示信息
                'tip.service.args.json': '请输入有效的 JSON 数组格式，例如：["-y", "@notionhq/notion-mcp-server"]',
                'tip.service.env.json': '请输入有效的 JSON 对象格式，例如：{"KEY": "value", "ANOTHER_KEY": "another_value"}',
                
                'form.proxy.name': '名称',
                'form.proxy.target': '源服务',
                'form.proxy.instructions': '用法说明',
                'form.proxy.endpoint': '代理端点',
                'form.proxy.type': '传输类型',
                'form.proxy.tools': '暴露的工具',
                'form.proxy.tools.help': '每行一个工具名称，留空表示全部暴露',
                'form.proxy.tools.selection': '可用工具选择',
                'form.proxy.autostart': '自动启动',
                'form.proxy.autostart.help': '勾选后，系统启动时将自动启动此代理',
                
                // 占位符文本
                'placeholder.service.name': '输入服务名称',
                'placeholder.service.command': 'uvx or npx',
                'placeholder.service.args': 'arg1\\narg2',
                'placeholder.service.env': 'KEY1=value1\\nKEY2=value2',
                'placeholder.proxy.name': '代理名称',
                'placeholder.proxy.endpoint': '/mcp',
                'placeholder.proxy.tools': '每行一个工具名称，留空表示全部暴露',
                'placeholder.proxy.target': '请选择源服务...',
                
                // 选项文本
                'option.type.stdio': '标准输入/输出 (stdio)',
                'option.type.sse': '服务器发送事件 (SSE)',
                'option.type.streamable': 'StreamableHTTP',
                'option.proxy.target.select': '请选择源服务...',
                
                // 提示信息
                'tip.proxy.endpoint': '对外暴露的端点路径，例如：/mcp',
                'tip.proxy.tools.selection': '(点击工具标签来选择/取消选择)',
                'tip.proxy.tools.help': '选中的工具将在代理中可用，默认全部选中',
                'tip.service.required': '必填项',
                'tip.no.data': '暂无数据',
                'tip.loading': '加载中...',
                
                // 成功消息
                'success.service.added': '服务添加成功',
                'success.service.updated': '服务更新成功',
                'success.service.deleted': '服务删除成功',
                'success.service.started': '服务启动成功',
                'success.service.stopped': '服务停止成功',
                'success.proxy.added': '代理添加成功',
                'success.proxy.updated': '代理更新成功',
                'success.proxy.deleted': '代理删除成功',
                'success.proxy.started': '代理启动成功',
                'success.proxy.stopped': '代理停止成功',
                'success.config.imported': '配置导入成功',
                'success.baseurl.saved': 'BASE URL 保存成功',
                'success.baseurl.reset': '已重置为默认BASE URL',
                
                // 错误消息
                'error.service.add': '添加服务失败',
                'error.service.update': '更新服务失败',
                'error.service.delete': '删除服务失败',
                'error.service.start': '启动服务失败',
                'error.service.stop': '停止服务失败',
                'error.proxy.add': '添加代理失败',
                'error.proxy.update': '更新代理失败',
                'error.proxy.delete': '删除代理失败',
                'error.proxy.start': '启动代理失败',
                'error.proxy.stop': '停止代理失败',
                'error.config.import': '配置导入失败',
                'error.baseurl.save': 'BASE URL 保存失败',
                'error.baseurl.reset': '重置配置失败',
                'error.network': '网络请求失败',
                'error.invalid.data': '数据格式无效',
                
                // 确认对话框
                'confirm.service.delete': '确定要删除服务 "{name}" 吗？',
                'confirm.proxy.delete': '确定要删除代理 "{name}" 吗？',
                'confirm.service.stop': '确定要停止服务 "{name}" 吗？',
                'confirm.proxy.stop': '确定要停止代理 "{name}" 吗？',

                // 导入配置
                'import.title': '导入 MCP 配置',
                'import.file.label': '选择配置文件 (JSON)',
                'import.file.placeholder': '未选择任何文件',
                'import.file.button': '选择文件',
                'import.button': '导入',

                // 动态内容
                'dynamic.tools.count': '{count} 个工具',
                'dynamic.no.tools': '暂无工具',
                'dynamic.copy.success': '已复制到剪贴板',
                'dynamic.copy.failed': '复制失败',
                'dynamic.copy.baseurl': '点击复制BASE URL',
                'dynamic.loading': '正在加载...',
                'dynamic.no.services': '暂无 MCP 服务，请点击右上角按钮添加',
                'dynamic.no.proxies': '暂无 MCP 代理，请点击右上角按钮添加',
                'dynamic.select.source': '请选择源服务...',
                'dynamic.updating': '更新中...',
                'dynamic.starting': '启动中...',
                'dynamic.stopping': '停止中...',
                'dynamic.restarting': '重启中...',
                'dynamic.saving': '保存中...',

                // 状态文本
                'status.running': '运行中',
                'status.stopped': '已停止',
                'status.error': '错误',
                'status.verified': '已验证',
                'status.connected': '已连接',
                'status.unknown': '未知',

                // 按钮文本
                'button.start': '启动',
                'button.stop': '停止',
                'button.restart': '重启',
                'button.edit': '编辑',
                'button.delete': '删除',
                'button.disconnect': '断开',
                'button.get.tools': '获取列表',
                'button.view.tools': '查看 {count} 个工具',
                'button.update.tools': '更新工具列表',

                // 自动启动状态
                'autostart.enabled': '已启用',
                'autostart.disabled': '未启用',
                'autostart.yes': '是',
                'autostart.no': '否',

                // 工具相关
                'tools.count': '{count} 个工具',
                'tools.modal.title': '{name} 工具列表',
                'tools.table.name': '名称',
                'tools.table.description': '描述',

                // 空状态消息
                'empty.services': '暂无 MCP 服务，请点击右上角按钮添加',
                'empty.proxies': '暂无 MCP 代理，请点击右上角按钮添加',

                // 确认对话框
                'confirm.proxy.delete': '确定要删除代理 "{name}" 吗？',

                // 测试功能
                'test.button': '测试连接',
                'test.button.testing': '测试中...',
                'test.results.title': '测试结果',
                'test.results.basic.info': '基本信息',
                'test.results.service.name': '服务名称',
                'test.results.transport.type': '传输类型',
                'test.results.status': '状态',
                'test.results.instructions': '用法说明',
                'test.results.tools': '可用工具',
                'test.results.tools.count': '可用工具 ({count} 个)',
                'test.results.no.tools': '暂无可用工具',
                'test.results.no.instructions': '无用法说明',

                // 默认值
                'default.no.instructions': '无用法说明',

                // 动作按钮
                'action.edit.instructions': '更改说明',
                'action.reset.instructions': '恢复默认说明',
                'action.save': '保存',
                'test.validation.name.required': '服务名称是必填项',
                'test.validation.type.required': '传输类型是必填项',
                'test.validation.command.required': 'stdio 传输需要命令',
                'test.validation.url.required': '远程传输需要 URL',
                'test.validation.url.invalid': 'URL 格式无效',

                // 语言切换
                'language.switch': '切换语言',
                'language.zh': '中文',
                'language.en': 'English'
            },
            en: {
                // Page titles and navigation
                'page.title': 'MCP-Dock',
                'nav.services': 'MCP Services',
                'nav.proxies': 'MCP Proxies',
                'sidebar.title': 'MCP-Dock',
                'sidebar.toggle': 'Toggle Sidebar',
                
                // Service management page
                'services.title': 'MCP Services',
                'services.add': 'Add Service',
                'services.import': 'Import Config',
                'services.refresh': 'Refresh List',
                'services.table.name': 'Name',
                'services.table.description': 'Description',
                'services.table.type': 'Type',
                'services.table.status': 'Status',
                'services.table.tools': 'Tools List',
                'services.table.actions': 'Actions',
                'services.table.autostart': 'Auto Start',
                
                // Proxy management page
                'proxies.title': 'MCP Proxies',
                'proxies.add': 'Add Proxy',
                'proxies.table.name': 'Name',
                'proxies.table.target': 'Source Service',
                'proxies.table.endpoint': 'Endpoint',
                'proxies.table.type': 'Type',
                'proxies.table.status': 'Status',
                'proxies.table.autostart': 'Auto Start',
                'proxies.table.access': 'Access Link',
                'proxies.table.tools': 'Tools List',
                'proxies.table.actions': 'Actions',
                
                // BASE URL configuration
                'baseurl.title': 'BASE URL Configuration',
                'baseurl.input.placeholder': 'Enter new BASE URL',
                'baseurl.save': 'Save Config',
                'baseurl.reset': 'Reset to Default',
                'baseurl.current': 'Current Active:',
                'baseurl.help': 'Configure the base URL for proxy services',
                
                // Status
                'status.running': 'Running',
                'status.stopped': 'Stopped',
                'status.connected': 'Connected',
                'status.error': 'Error',
                'status.verified': 'Verified',
                'status.loading': 'Loading',
                
                // Action buttons
                'action.start': 'Start',
                'action.stop': 'Stop',
                'action.restart': 'Restart',
                'action.edit': 'Edit',
                'action.delete': 'Delete',
                'action.save': 'Save',
                'action.cancel': 'Cancel',
                'action.close': 'Close',
                'action.confirm': 'Confirm',
                'action.update': 'Update',
                'action.import': 'Import',
                'action.export': 'Export',
                
                // Modal titles
                'modal.add.service': 'Add MCP Service',
                'modal.edit.service': 'Edit MCP Service',
                'modal.add.proxy': 'Add MCP Proxy',
                'modal.edit.proxy': 'Edit MCP Proxy',
                'modal.import.config': 'Import MCP Configuration',
                
                // Form labels
                'form.service.name': 'Service Name',
                'form.service.type': 'Transport Type',
                'form.service.command': 'Command',
                'form.service.args': 'Arguments',
                'form.service.args.json': 'Arguments (JSON Array Format)',
                'form.service.env': 'Environment Variables',
                'form.service.env.json': 'Environment Variables (JSON Object Format)',
                'form.service.cwd': 'Working Directory',
                'form.service.cwd.optional': 'Working Directory (Optional)',
                'form.service.url': 'URL',
                'form.service.headers': 'Request Headers',
                'form.service.instructions': 'Instructions',
                'form.service.autostart': 'Auto Start',
                'form.service.autostart.help': 'When checked, this service will start automatically on system startup',

                // Tip messages
                'tip.service.args.json': 'Please enter valid JSON array format, e.g.: ["-y", "@notionhq/notion-mcp-server"]',
                'tip.service.env.json': 'Please enter valid JSON object format, e.g.: {"KEY": "value", "ANOTHER_KEY": "another_value"}',

                'form.proxy.name': 'Name',
                'form.proxy.target': 'Source Service',
                'form.proxy.instructions': 'Instructions',
                'form.proxy.endpoint': 'Proxy Endpoint',
                'form.proxy.type': 'Transport Type',
                'form.proxy.tools': 'Exposed Tools',
                'form.proxy.tools.help': 'One tool name per line, leave empty to expose all',
                'form.proxy.tools.selection': 'Available Tool Selection',
                'form.proxy.autostart': 'Auto Start',
                'form.proxy.autostart.help': 'When checked, this proxy will start automatically on system startup',
                
                // Placeholder text
                'placeholder.service.name': 'Enter service name',
                'placeholder.service.command': 'uvx or npx',
                'placeholder.service.args': 'arg1\\narg2',
                'placeholder.service.args.json': 'e.g.: ["--arg1", "value1", "--arg2"]',
                'placeholder.service.env': 'KEY1=value1\\nKEY2=value2',
                'placeholder.service.env.json': 'e.g.: {"VAR1": "value1", "VAR2": "value2"}',
                'placeholder.service.cwd': 'Working directory path',
                'placeholder.service.url': 'http://localhost:3000/sse',
                'placeholder.service.headers': 'Content-Type=application/json\\nAuthorization=Bearer token',
                'placeholder.proxy.name': 'Proxy name',
                'placeholder.proxy.endpoint': '/mcp',
                'placeholder.proxy.tools': 'One tool name per line, leave empty to expose all',
                'placeholder.proxy.target': 'Please select source service...',
                
                // Option text
                'option.type.stdio': 'Standard Input/Output (stdio)',
                'option.type.sse': 'Server-Sent Events (SSE)',
                'option.type.streamable': 'StreamableHTTP',
                'option.proxy.target.select': 'Please select source service...',
                
                // Tips
                'tip.proxy.endpoint': 'External endpoint path, e.g.: /mcp',
                'tip.proxy.tools.selection': '(Click tool tags to select/deselect)',
                'tip.proxy.tools.help': 'Selected tools will be available in the proxy, all selected by default',
                'tip.service.args.json': 'e.g.: ["--arg1", "value1", "--arg2"]',
                'tip.service.env.json': 'e.g.: {"VAR1": "value1", "VAR2": "value2"}',
                'tip.service.required': 'Required field',
                'tip.no.data': 'No data available',
                'tip.loading': 'Loading...',

                // Tool related
                'tool.unknown': 'Unknown Tool',
                
                // Success messages
                'success.service.added': 'Service added successfully',
                'success.service.updated': 'Service updated successfully',
                'success.service.deleted': 'Service deleted successfully',
                'success.service.started': 'Service started successfully',
                'success.service.stopped': 'Service stopped successfully',
                'success.proxy.added': 'Proxy added successfully',
                'success.proxy.updated': 'Proxy updated successfully',
                'success.proxy.deleted': 'Proxy {name} deleted successfully',
                'success.proxy.started': 'Proxy started successfully',
                'success.proxy.stopped': 'Proxy stopped successfully',
                'success.proxy.tools.updated': 'Proxy {name} tools list updated successfully, {count} tools total',
                'success.config.imported': 'Configuration imported successfully',
                'success.baseurl.saved': 'BASE URL saved successfully',
                'success.baseurl.reset': 'Reset to default BASE URL',
                
                // Error messages
                'error.service.add': 'Failed to add service',
                'error.service.update': 'Failed to update service',
                'error.service.delete': 'Failed to delete service',
                'error.service.start': 'Failed to start service',
                'error.service.stop': 'Failed to stop service',
                'error.service.test': 'Failed to test service',
                'error.service.info.load': 'Failed to load service information',
                'error.form.incomplete': 'Please fill in the required service information first',
                'error.proxy.add': 'Failed to add proxy',
                'error.proxy.update': 'Failed to update proxy',
                'error.proxy.delete': 'Failed to delete proxy {name}',
                'error.proxy.start': 'Failed to start proxy',
                'error.proxy.stop': 'Failed to stop proxy',
                'error.proxy.tools.update': 'Failed to update proxy {name} tools list',
                'error.config.import': 'Failed to import configuration',
                'error.baseurl.save': 'Failed to save BASE URL',
                'error.baseurl.reset': 'Failed to reset configuration',
                'error.network': 'Network request failed',
                'error.invalid.data': 'Invalid data format',
                
                // Confirmation dialogs
                'confirm.service.delete': 'Are you sure you want to delete service "{name}"?',
                'confirm.proxy.delete': 'Are you sure you want to delete proxy "{name}"?',
                'confirm.service.stop': 'Are you sure you want to stop service "{name}"?\\n\\nYou will need to manually restart it after stopping.',
                'confirm.service.restart': 'Are you sure you want to restart service "{name}"?\\n\\nThe service will be temporarily unavailable during restart.',
                'confirm.proxy.stop': 'Are you sure you want to stop proxy "{name}"?',
                'confirm.proxy.restart': 'Are you sure you want to restart proxy "{name}"?\\n\\nThe proxy will be temporarily unavailable during restart.',

                // Import configuration
                'import.title': 'Import MCP Configuration',
                'import.file.label': 'Select Configuration File (JSON)',
                'import.file.placeholder': 'No file selected',
                'import.file.button': 'Choose File',
                'import.button': 'Import',

                // Dynamic content
                'dynamic.tools.count': '{count} tools',
                'dynamic.no.tools': 'No tools available',
                'dynamic.copy.success': 'Copied to clipboard',
                'dynamic.copy.failed': 'Copy failed',
                'dynamic.copy.baseurl': 'Click to copy BASE URL',
                'dynamic.loading': 'Loading...',
                'dynamic.no.services': 'No MCP services available, click the button in the top right to add one',
                'dynamic.no.proxies': 'No MCP proxies available, click the button in the top right to add one',
                'dynamic.select.source': 'Please select source service...',
                'dynamic.updating': 'Updating...',
                'dynamic.starting': 'Starting...',
                'dynamic.stopping': 'Stopping...',
                'dynamic.restarting': 'Restarting...',
                'dynamic.saving': 'Saving...',

                // Status text
                'status.running': 'Running',
                'status.stopped': 'Stopped',
                'status.error': 'Error',
                'status.verified': 'Verified',
                'status.connected': 'Connected',
                'status.enabled': 'Enabled',
                'status.disabled': 'Disabled',
                'status.unknown': 'Unknown',

                // Button text
                'button.start': 'Start',
                'button.stop': 'Stop',
                'button.restart': 'Restart',
                'button.edit': 'Edit',
                'button.delete': 'Delete',
                'button.disconnect': 'Disconnect',
                'button.get.tools': 'Get List',
                'button.view.tools': 'View {count} tools',
                'button.update.tools': 'Update Tools List',

                // Action text
                'action.edit.instructions': 'Change Instructions',
                'action.reset.instructions': 'Restore Default Instructions',
                'action.select.all': 'Select All',
                'action.deselect.all': 'Deselect All',

                // Auto-start status
                'autostart.enabled': 'Enabled',
                'autostart.disabled': 'Disabled',
                'autostart.yes': 'Yes',
                'autostart.no': 'No',

                // Tools related
                'tools.count': '{count} tools',
                'tools.modal.title': '{name} Tools List',
                'tools.table.name': 'Name',
                'tools.table.description': 'Description',

                // Empty state messages
                'empty.services': 'No MCP services available. Click the button in the top right to add one.',
                'empty.proxies': 'No MCP proxies available. Click the button in the top right to add one.',

                // Confirmation dialogs
                'confirm.proxy.delete': 'Are you sure you want to delete proxy "{name}"?',

                // Test functionality
                'test.button': 'Test Connection',
                'test.button.testing': 'Testing...',
                'test.results.title': 'Test Results',
                'test.results.basic.info': 'Basic Information',
                'test.results.service.name': 'Service Name',
                'test.results.transport.type': 'Transport Type',
                'test.results.status': 'Status',
                'test.results.instructions': 'Instructions',
                'test.results.tools': 'Available Tools',
                'test.results.tools.count': 'Available Tools ({count} items)',
                'test.results.no.tools': 'No tools available',
                'test.results.no.instructions': 'No instructions',

                // Default values
                'default.no.instructions': 'No Instructions',

                // Action buttons
                'action.edit.instructions': 'Change Instructions',
                'action.reset.instructions': 'Restore Default Instructions',
                'action.save': 'Save',
                'test.validation.name.required': 'Service name is required',
                'test.validation.type.required': 'Transport type is required',
                'test.validation.command.required': 'Command is required for stdio transport',
                'test.validation.url.required': 'URL is required for remote transport',
                'test.validation.url.invalid': 'Invalid URL format',

                // Language switching
                'language.switch': 'Switch Language',
                'language.zh': '中文',
                'language.en': 'English'
            }
        };
        
        this.init();
    }
    
    init() {
        // 检测浏览器语言
        this.detectLanguage();
        // 应用翻译
        this.applyTranslations();
        // 添加语言切换按钮
        this.addLanguageSwitcher();
    }
    
    detectLanguage() {
        // 首先检查localStorage中的用户偏好
        const savedLanguage = localStorage.getItem('mcp-dock-language');
        if (savedLanguage && this.translations[savedLanguage]) {
            this.currentLanguage = savedLanguage;
            return;
        }
        
        // 检测浏览器语言
        const browserLanguage = navigator.language || navigator.userLanguage;
        if (browserLanguage.startsWith('zh')) {
            this.currentLanguage = 'zh';
        } else {
            this.currentLanguage = 'en';
        }
        
        // 保存到localStorage
        localStorage.setItem('mcp-dock-language', this.currentLanguage);
    }
    
    t(key, params = {}) {
        let translation = this.translations[this.currentLanguage][key] || key;
        
        // 替换参数
        Object.keys(params).forEach(param => {
            translation = translation.replace(`{${param}}`, params[param]);
        });
        
        return translation;
    }
    
    setLanguage(language) {
        if (this.translations[language]) {
            this.currentLanguage = language;
            localStorage.setItem('mcp-dock-language', language);
            this.applyTranslations();
            this.updateLanguageSwitcher();
        }
    }

    updateLanguageSwitcher() {
        // 更新语言切换下拉选择框的状态
        this.updateLanguageSelectDisplay();
    }
    
    applyTranslations() {
        // 更新页面标题
        document.title = this.t('page.title');

        // 更新所有带有data-i18n属性的元素
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = this.t(key);
        });

        // 更新所有带有data-i18n-placeholder属性的元素
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.t(key);
        });

        // 更新所有带有data-i18n-title属性的元素
        document.querySelectorAll('[data-i18n-title]').forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            element.title = this.t(key);
        });

        // 刷新表格内容以应用新的翻译
        if (typeof loadServersList === 'function') {
            loadServersList();
        }
        if (typeof loadProxiesList === 'function') {
            loadProxiesList();
        }
    }
    
    addLanguageSwitcher() {
        // 在侧边栏底部添加语言切换下拉选择框
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            const languageSwitcher = document.createElement('div');
            languageSwitcher.className = 'language-switcher p-3 border-top';
            languageSwitcher.innerHTML = `
                <select class="form-select form-select-sm language-select" id="languageSelect" onchange="i18n.handleLanguageChange(this)">
                    <option value="zh" ${this.currentLanguage === 'zh' ? 'selected' : ''}>
                        <span class="flag-text">🇨🇳 中文</span>
                    </option>
                    <option value="en" ${this.currentLanguage === 'en' ? 'selected' : ''}>
                        <span class="flag-text">🇺🇸 English</span>
                    </option>
                </select>
            `;
            sidebar.appendChild(languageSwitcher);

            // 初始化选择框显示
            this.updateLanguageSelectDisplay();
        }
    }

    handleLanguageChange(selectElement) {
        const selectedLanguage = selectElement.value;
        this.setLanguage(selectedLanguage);
    }

    updateLanguageSelectDisplay() {
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            // 更新选中状态
            languageSelect.value = this.currentLanguage;

            // 根据侧边栏状态更新显示
            const sidebar = document.querySelector('.sidebar');
            const isCollapsed = sidebar && sidebar.classList.contains('collapsed');

            if (isCollapsed) {
                // 收缩状态：只显示国旗
                languageSelect.innerHTML = `
                    <option value="zh" ${this.currentLanguage === 'zh' ? 'selected' : ''}>🇨🇳</option>
                    <option value="en" ${this.currentLanguage === 'en' ? 'selected' : ''}>🇺🇸</option>
                `;
            } else {
                // 展开状态：显示国旗+文字
                languageSelect.innerHTML = `
                    <option value="zh" ${this.currentLanguage === 'zh' ? 'selected' : ''}>🇨🇳 中文</option>
                    <option value="en" ${this.currentLanguage === 'en' ? 'selected' : ''}>🇺🇸 English</option>
                `;
            }
            languageSelect.value = this.currentLanguage;
        }
    }
}

// 创建全局i18n实例
const i18n = new I18n();

// 导出供其他模块使用
window.i18n = i18n;

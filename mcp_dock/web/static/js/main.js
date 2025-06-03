/**
 * MCP 统一管理工具 WebUI 交互脚本
 */

// 侧边栏管理器
const SidebarManager = {
    // 本地存储键名
    STORAGE_KEY: 'mcp_dock_sidebar_collapsed',

    // 初始化侧边栏
    init: function() {
        this.loadState();
        this.bindEvents();
        this.updateResponsiveState();

        // 监听窗口大小变化
        $(window).on('resize', () => {
            this.updateResponsiveState();
        });
    },

    // 从本地存储加载状态
    loadState: function() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            const isCollapsed = stored === 'true';

            // 根据屏幕尺寸设置默认状态
            const screenWidth = $(window).width();
            if (screenWidth >= 992) {
                // 桌面端：使用存储的状态，默认展开
                this.setSidebarState(isCollapsed);
            } else if (screenWidth >= 768) {
                // 平板端：默认收缩
                this.setSidebarState(true);
            } else {
                // 移动端：隐藏侧边栏
                this.setSidebarState(false, true);
            }
        } catch (e) {
            console.warn('加载侧边栏状态失败:', e);
            this.setSidebarState(false);
        }
    },

    // 保存状态到本地存储
    saveState: function(isCollapsed) {
        try {
            localStorage.setItem(this.STORAGE_KEY, isCollapsed.toString());
        } catch (e) {
            console.error('保存侧边栏状态失败:', e);
        }
    },

    // 设置侧边栏状态
    setSidebarState: function(isCollapsed, isMobile = false) {
        const $sidebar = $('#sidebar');
        const $mainContent = $('#mainContent');
        const $toggleBtn = $('#sidebarToggle');

        if (isMobile) {
            // 移动端：隐藏侧边栏
            $sidebar.removeClass('collapsed show');
            // 移动端的样式由CSS媒体查询处理，不需要手动设置margin-left
        } else if (isCollapsed) {
            // 收缩状态
            $sidebar.addClass('collapsed').removeClass('show');
            // CSS会自动处理margin-left和width的变化
            $toggleBtn.find('i').removeClass('fas fa-angle-double-left').addClass('fas fa-angle-double-right');
            $toggleBtn.attr('title', '展开侧边栏');
        } else {
            // 展开状态
            $sidebar.removeClass('collapsed show');
            // CSS会自动处理margin-left和width的变化
            $toggleBtn.find('i').removeClass('fas fa-angle-double-right').addClass('fas fa-angle-double-left');
            $toggleBtn.attr('title', '收缩侧边栏');
        }

        // 更新语言选择器显示
        if (typeof window.i18n !== 'undefined' && window.i18n.updateLanguageSelectDisplay) {
            setTimeout(() => {
                window.i18n.updateLanguageSelectDisplay();
            }, 300); // 等待CSS动画完成
        }
    },

    // 切换侧边栏状态
    toggle: function() {
        const $sidebar = $('#sidebar');
        const screenWidth = $(window).width();

        if (screenWidth < 992) {
            // 移动端/平板端：显示/隐藏侧边栏
            const isVisible = $sidebar.hasClass('show');
            if (isVisible) {
                this.hideMobileSidebar();
            } else {
                this.showMobileSidebar();
            }
        } else {
            // 桌面端：展开/收缩侧边栏
            const isCollapsed = $sidebar.hasClass('collapsed');
            this.setSidebarState(!isCollapsed);
            this.saveState(!isCollapsed);
        }
    },

    // 显示移动端侧边栏
    showMobileSidebar: function() {
        $('#sidebar').addClass('show');
        $('#sidebarOverlay').addClass('show');
        $('body').css('overflow', 'hidden');
    },

    // 隐藏移动端侧边栏
    hideMobileSidebar: function() {
        $('#sidebar').removeClass('show');
        $('#sidebarOverlay').removeClass('show');
        $('body').css('overflow', '');
    },

    // 更新响应式状态
    updateResponsiveState: function() {
        const screenWidth = $(window).width();
        const $sidebar = $('#sidebar');

        if (screenWidth < 992) {
            // 移动端/平板端：重置为隐藏状态
            this.hideMobileSidebar();
            // 移动端的样式由CSS媒体查询处理，不需要手动设置margin-left
        } else {
            // 桌面端：恢复正常状态
            this.hideMobileSidebar();
            const isCollapsed = $sidebar.hasClass('collapsed');
            this.setSidebarState(isCollapsed);
        }
    },

    // 绑定事件
    bindEvents: function() {
        // 侧边栏切换按钮
        $('#sidebarToggle').on('click', () => {
            this.toggle();
        });

        // 移动端菜单切换按钮
        $('#mobileMenuToggle').on('click', () => {
            this.toggle();
        });

        // 遮罩层点击关闭
        $('#sidebarOverlay').on('click', () => {
            this.hideMobileSidebar();
        });

        // 导航链接点击处理
        $('#sidebar .nav-link').on('click', (e) => {
            e.preventDefault();

            const $link = $(e.currentTarget);
            const target = $link.data('bs-target');

            // 更新导航状态
            $('#sidebar .nav-link').removeClass('active');
            $link.addClass('active');

            // 切换标签页
            $('.tab-pane').removeClass('show active');
            $(target).addClass('show active');

            // 加载对应的数据
            if (target === '#serversTab') {
                loadServersList();
            } else if (target === '#proxiesTab') {
                loadProxiesList();
            }

            // 移动端自动关闭侧边栏
            if ($(window).width() < 992) {
                this.hideMobileSidebar();
            }
        });

        // 键盘导航支持
        $(document).on('keydown', (e) => {
            // Ctrl/Cmd + B 切换侧边栏
            if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
                e.preventDefault();
                this.toggle();
            }

            // ESC 关闭移动端侧边栏
            if (e.key === 'Escape' && $(window).width() < 992) {
                this.hideMobileSidebar();
            }
        });
    }
};

// 全局Toast函数，兼容所有调用
function showToast(type, message) {
    $('#toastMessage').text(message);
    $('#toast').removeClass('bg-success bg-danger bg-info bg-warning');
    if (type === 'success') $('#toast').addClass('bg-success');
    else if (type === 'danger') $('#toast').addClass('bg-danger');
    else if (type === 'info') $('#toast').addClass('bg-info');
    else if (type === 'warning') $('#toast').addClass('bg-warning');
    const toast = new bootstrap.Toast(document.getElementById('toast'));
    toast.show();
}

// 全局变量，存储服务器基础URL
let baseServerUrl = window.location.origin;
let customBaseUrl = null; // 用户自定义的BASE URL

// BASE URL 配置管理
const BaseUrlManager = {
    // 本地存储键名
    STORAGE_KEY: 'mcp_dock_base_url',

    // 获取当前生效的BASE URL
    getEffectiveBaseUrl: function() {
        return customBaseUrl || baseServerUrl;
    },

    // 从本地存储加载配置
    loadFromStorage: function() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (stored) {
                customBaseUrl = stored;
                return customBaseUrl;
            }
        } catch (e) {
            console.warn('加载BASE URL配置失败:', e);
        }
        return null;
    },

    // 保存配置到本地存储
    saveToStorage: function(url) {
        try {
            if (url && url.trim()) {
                localStorage.setItem(this.STORAGE_KEY, url.trim());
                customBaseUrl = url.trim();
            } else {
                localStorage.removeItem(this.STORAGE_KEY);
                customBaseUrl = null;
            }
            return true;
        } catch (e) {
            console.error('保存BASE URL配置失败:', e);
            return false;
        }
    },

    // 验证URL格式
    validateUrl: function(url) {
        if (!url || !url.trim()) {
            return { valid: true, message: '' }; // 空URL是有效的（使用默认）
        }

        try {
            const urlObj = new URL(url.trim());
            if (!['http:', 'https:'].includes(urlObj.protocol)) {
                return { valid: false, message: '只支持 HTTP 和 HTTPS 协议' };
            }
            return { valid: true, message: '' };
        } catch (e) {
            return { valid: false, message: '请输入有效的URL格式' };
        }
    },

    // 更新界面显示
    updateUI: function() {
        $('#baseUrlInput').val(customBaseUrl || '');

        // 更新代理列表中的访问链接
        this.updateProxyLinks();
    },

    // 更新代理列表中的访问链接
    updateProxyLinks: function() {
        const effectiveUrl = this.getEffectiveBaseUrl();
        $('#proxiesList tr').each(function() {
            const $row = $(this);
            const $urlInput = $row.find('input[readonly]');
            if ($urlInput.length > 0) {
                const currentUrl = $urlInput.val();
                // 提取代理名称和端点
                const urlParts = currentUrl.split('/');
                if (urlParts.length >= 4) {
                    const proxyName = urlParts[urlParts.length - 2];
                    const endpoint = '/' + urlParts[urlParts.length - 1];
                    const newUrl = `${effectiveUrl}/${proxyName}${endpoint}`;
                    $urlInput.val(newUrl);

                    // 更新复制按钮的data-url属性
                    const $copyBtn = $row.find('.copy-url-btn');
                    if ($copyBtn.length > 0) {
                        $copyBtn.attr('data-url', newUrl);
                        $copyBtn.data('url', newUrl);
                    }
                }
            }
        });
    }
};

// 全局错误处理
window.addEventListener('error', function(e) {
    console.error('全局JavaScript错误:', e.error);
    console.error('错误信息:', e.message);
    console.error('错误位置:', e.filename + ':' + e.lineno + ':' + e.colno);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('未处理的Promise拒绝:', e.reason);
});

$(document).ready(function() {
    // 等待国际化系统初始化完成
    if (typeof window.i18n !== 'undefined') {
        // 应用国际化翻译
        window.i18n.applyTranslations();

        // 为动态内容添加翻译支持
        window.translateDynamicContent = function() {
            if (typeof window.i18n !== 'undefined') {
                window.i18n.applyTranslations();
            }
        };
    }

    // 初始化侧边栏
    SidebarManager.init();

    // 初始化BASE URL配置
    BaseUrlManager.loadFromStorage();
    BaseUrlManager.updateUI();

    // BASE URL配置事件处理
    $('#saveBaseUrlBtn').click(function() {
        const inputUrl = $('#baseUrlInput').val().trim();
        const validation = BaseUrlManager.validateUrl(inputUrl);

        if (!validation.valid) {
            showToast('danger', validation.message);
            return;
        }

        if (BaseUrlManager.saveToStorage(inputUrl)) {
            BaseUrlManager.updateUI();
            showToast('success', inputUrl ? window.i18n.t('success.baseurl.saved') : window.i18n.t('success.baseurl.reset'));
        } else {
            showToast('danger', window.i18n.t('error.baseurl.save'));
        }
    });

    $('#resetBaseUrlBtn').click(function() {
        $('#baseUrlInput').val('');
        if (BaseUrlManager.saveToStorage('')) {
            BaseUrlManager.updateUI();
            showToast('success', window.i18n.t('success.baseurl.reset'));
        } else {
            showToast('danger', window.i18n.t('error.baseurl.reset'));
        }
    });


    

    
    // 注意：导航链接点击事件现在由 SidebarManager 处理
    
    // 检查Bootstrap是否可用
    if (typeof bootstrap === 'undefined') {
        console.error('Bootstrap is not loaded!');
        return;
    }

    // 模态框对象 - 添加错误处理
    let addServerModal, editServerModal, importConfigModal, addProxyModal, editProxyModal, toast;

    try {
        addServerModal = new bootstrap.Modal(document.getElementById('addServerModal'));
        editServerModal = new bootstrap.Modal(document.getElementById('editServerModal'));
        importConfigModal = new bootstrap.Modal(document.getElementById('importConfigModal'));
        addProxyModal = new bootstrap.Modal(document.getElementById('addProxyModal'));
        editProxyModal = new bootstrap.Modal(document.getElementById('editProxyModal'));
        toast = new bootstrap.Toast(document.getElementById('toast'));
    } catch (error) {
        console.error('Bootstrap模态框初始化失败:', error);
        return;
    }

    // 加载服务器列表
    loadServersList();

    // 加载代理列表
    loadProxiesList();
    
    // 注意：标签切换事件现在由 SidebarManager 处理
    
    // 注意：按钮现在已经移动到各自的页面内部，无需切换显示状态
    
    // 显示添加服务器模态框
    $('#addServerBtn').click(function() {
        // 重置表单
        $('#addServerForm')[0].reset();
        addServerModal.show();
    });
    
    // 显示添加代理模态框
    $('#addProxyBtn').click(function() {
        // 重置表单
        $('#addProxyForm')[0].reset();

        // 加载可用服务列表
        $.ajax({
            url: '/api/servers',
            type: 'GET',
            cache: false,
            dataType: 'json',
            success: function(response) {
                const $serverSelect = $('#proxyServerName');
                $serverSelect.empty();

                // 添加"请选择"选项
                $serverSelect.append($('<option>').val('').text(window.i18n.t('dynamic.select.source')));

                // 添加可用的服务
                if (response && Array.isArray(response)) {
                    response.forEach(function(server) {
                        const option = $('<option>')
                            .val(server.name)
                            .text(server.name);
                        $serverSelect.append(option);
                    });
                }

                // 显示模态框
                const addProxyModal = new bootstrap.Modal(document.getElementById('addProxyModal'));
                addProxyModal.show();
            },
            error: function(xhr) {
                console.error('获取服务列表失败:', xhr.responseText);
                showToast('danger', '获取可用服务列表失败，请刷新后重试');
            }
        });
    });
    
    // 类型切换动态显示/隐藏字段
    function updateServerFormFields() {
        const type = $('#transportType').val();
        if (type === 'stdio') {
            $('#stdioFields').show();
            $('#httpFields').hide();
            // 设置stdio类型的自动启动文本
            $('#autoStartLabel').text('自动启动');
            $('#autoStartText').text('勾选后，系统启动时将自动启动此服务');
        } else {
            $('#stdioFields').hide();
            $('#httpFields').show();
            // 设置HTTP类型的自动连接文本
            $('#autoStartLabel').text('自动连接');
            $('#autoStartText').text('勾选后，系统启动时将自动连接此远程服务');
        }
    }
    $('#transportType').on('change', updateServerFormFields);
    updateServerFormFields();
    
    // 编辑服务器模态框类型切换
    function updateEditServerFormFields() {
        const type = $('#editTransportType').val();
        if (type === 'stdio') {
            $('#editStdioFields').show();
            $('#editHttpFields').hide();
            // 设置stdio类型的自动启动文本
            $('#editAutoStartLabel').text('自动启动');
            $('#editAutoStartText').text('勾选后，系统启动时将自动启动此服务');
        } else {
            $('#editStdioFields').hide();
            $('#editHttpFields').show();
            // 设置HTTP类型的自动连接文本
            $('#editAutoStartLabel').text('自动连接');
            $('#editAutoStartText').text('勾选后，系统启动时将自动连接此远程服务');
        }
    }
    $('#editTransportType').on('change', updateEditServerFormFields);
    updateEditServerFormFields();
    
    // 保存按钮处理
    $('#saveServerBtn').off('click').on('click', function() {
        const type = $('#transportType').val();
        const formData = new FormData();
        formData.append('name', $('#serverName').val());
        formData.append('desc', $('#serverDesc').val());
        formData.append('transport_type', type);
        
        // 处理自动启动/连接选项(适用于所有服务类型)
        formData.append('auto_start', $('#autoStart').prop('checked'));
        

        if (type === 'stdio') {
            formData.append('command', $('#command').val());
            // 参数
            const argsArr = $('#args').val().split('\n').map(s => s.trim()).filter(Boolean);
            formData.append('args', JSON.stringify(argsArr));
            // 环境变量
            const envLines = $('#env').val().split('\n').map(s => s.trim()).filter(Boolean);
            const envObj = {};
            envLines.forEach(line => {
                const idx = line.indexOf('=');
                if (idx > 0) envObj[line.slice(0, idx)] = line.slice(idx + 1);
            });
            formData.append('env', JSON.stringify(envObj));
            formData.append('url', '');
            formData.append('headers', '');
        } else {
            formData.append('command', '');
            formData.append('args', '[]');
            formData.append('env', '{}');
            formData.append('url', $('#url').val());
        }
        
        // 表单验证
        if (!formData.get('name')) {
            showToast('danger', '请输入服务名称');
            return;
        }
        
        if (!formData.get('transport_type')) {
            showToast('danger', '请选择传输类型');
            return;
        }
        
        if (formData.get('transport_type') === 'stdio' && !formData.get('command')) {
            showToast('danger', '请输入命令');
            return;
        }
        
        if ((formData.get('transport_type') === 'sse' || formData.get('transport_type') === 'streamableHTTP') && !formData.get('url')) {
            showToast('danger', '请输入URL');
            return;
        }
        
        // 校验
        if (!$('#serverName').val()) {
            showToast('danger', '名称为必填项');
            $('#serverName').focus();
            return;
        }
        if (formData.get('transport_type') === 'stdio' && !$('#command').val()) {
            showToast('danger', '命令为必填项');
            $('#command').focus();
            return;
        }
        if ((formData.get('transport_type') === 'sse' || formData.get('transport_type') === 'streamableHTTP') && !$('#url').val()) {
            showToast('danger', 'URL为必填项');
            $('#url').focus();
            return;
        }
        $.ajax({
            url: '/api/servers',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                addServerModal.hide();
                showToast('success', response.message);
                loadServersList();
            },
            error: function(xhr) {
                let errorMsg = '添加服务器失败';
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);
            }
        });
    });
    
    // 编辑服务器
    $(document).on('click', '.edit-server-btn', function() {
        const serverName = $(this).data('server');
        
        // 显示加载指示器
        const $btn = $(this);
        const originalHtml = $btn.html();
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i>');
        
        // 获取服务器信息并填充表单
        $.ajax({
            url: `/api/servers/${serverName}`,
            type: 'GET',
            success: function(server) {
                // 重置按钮状态
                $btn.html(originalHtml);
                $btn.prop('disabled', false);
                

                
                // 填充基本字段
                $('#editServerOriginalName').val(server.name);
                $('#editServerName').val(server.name);
                $('#editCommand').val(server.command);
                $('#editArgs').val(JSON.stringify(server.args || []));
                
                // 使用直接获取的服务器信息填充其他字段
                $('#editEnv').val(JSON.stringify(server.env || {}));
                $('#editCwd').val(server.cwd || '');
                $('#editTransportType').val(server.transport_type || 'stdio').trigger('change');
                $('#editPort').val(server.port || '');
                $('#editUrl').val(server.url || '');
                $('#editHeaders').val(
                  server.headers && Object.keys(server.headers).length > 0
                    ? JSON.stringify(server.headers, null, 2)
                    : ''
                );
                
                // 填充自动启动选项
                if (server.auto_start !== undefined) {
                    $('#editAutoStart').prop('checked', server.auto_start);
                } else {
                    $('#editAutoStart').prop('checked', false);
                }
                
                // 显示模态框
                editServerModal.show();
            },
            error: function(xhr) {
                // 重置按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);
                
                console.error('获取服务器信息失败:', xhr.responseText);
                showToast('danger', '获取服务器信息失败');
            }
        });
    });
    
    // 提交更新服务器表单
    $('#updateServerBtn').click(function() {
        const originalName = $('#editServerOriginalName').val();
        
        // 禁用按钮防止重复提交
        const $btn = $(this);
        const originalHtml = $btn.html();
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.updating'));
        
        try {
            // 接收环境变量字段，预先检查是否是有效JSON
            const envText = $('#editEnv').val().trim();
            if (envText) {
                try {
                    // 验证JSON格式
                    JSON.parse(envText);
                } catch(e) {
                    showToast('danger', '环境变量不是有效的JSON格式: ' + e.message);
                    $btn.prop('disabled', false);
                    $btn.html(originalHtml);
                    return;
                }
            }
            
            // 接收参数字段，预先检查是否是有效JSON
            const argsText = $('#editArgs').val().trim();
            let argsArray = [];
            if (argsText) {
                try {
                    // 先尝试 JSON 解析
                    argsArray = JSON.parse(argsText);
                    if (!Array.isArray(argsArray)) throw new Error('参数不是数组');
                } catch(e) {
                    // 尝试多行或空格分割
                    if (argsText.includes('\n')) {
                        argsArray = argsText.split('\n').map(s => s.trim()).filter(Boolean);
                    } else if (argsText.includes(' ')) {
                        argsArray = argsText.split(' ').map(s => s.trim()).filter(Boolean);
                    } else if (argsText.length > 0) {
                        argsArray = [argsText];
                    } else {
                        showToast('danger', '参数不能为空');
                        $btn.prop('disabled', false);
                        $btn.html(originalHtml);
                        return;
                    }
                }
            }
            // 用 JSON 字符串传给后端
            $('#editArgs').val(JSON.stringify(argsArray));
        
            // 使用FormData收集表单数据
            const formData = new FormData($('#editServerForm')[0]);
            
            // 处理自动启动/连接选项
            // 无论什么类型服务，都提交auto_start参数
            formData.set('auto_start', $('#editAutoStart').prop('checked'));
            
            const transportType = $('#editTransportType').val();
            
            $.ajax({
                url: `/api/servers/${originalName}`,
                type: 'PUT',
                data: formData,
                processData: false,
                contentType: false,
                success: function(response) {
                    // 恢复按钮状态
                    $btn.prop('disabled', false);
                    $btn.html(originalHtml);
                    
                    editServerModal.hide();
                    showToast('success', response.message);
                    loadServersList();
                },
                error: function(xhr, status, error) {
                    // 恢复按钮状态
                    $btn.prop('disabled', false);
                    $btn.html(originalHtml);
                    
                    console.error('更新失败:', xhr.responseText);
                    let errorMsg = 'Failed to update server';
                    try {
                        const resp = JSON.parse(xhr.responseText);
                        errorMsg = resp.detail || errorMsg;
                    } catch(e) {
                        if (xhr.responseJSON && xhr.responseJSON.detail) {
                            errorMsg += ': ' + xhr.responseJSON.detail;
                        } else {
                            errorMsg += ': ' + error;
                        }
                    }
                    showToast('danger', errorMsg);
                }
            });
        } catch (e) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            
            console.error('表单处理异常:', e);
            showToast('danger', '表单提交异常: ' + e.message);
        }
    });
    
    // 删除服务器
    $(document).on('click', '.delete-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i>');
        if (confirm(window.i18n.t('confirm.service.delete', {name: serverName}))) {
            $.ajax({
                url: `/api/servers/${serverName}`,
                type: 'DELETE',
                success: function(response) {
                    showToast('success', response.message);
                    loadServersList();
                },
                error: function(xhr) {
                    let errorMsg = '删除服务器失败';
                    if (xhr.responseJSON && xhr.responseJSON.detail) {
                        errorMsg += ': ' + xhr.responseJSON.detail;
                    }
                    showToast('danger', errorMsg);
                    $btn.prop('disabled', false);
                    $btn.html('<i class="fas fa-trash"></i> 删除');
                    loadServersList();
                }
            });
        } else {
            $btn.prop('disabled', false);
            $btn.html('<i class="fas fa-trash"></i> 删除');
        }
    });
    
    // 启动服务器
    $(document).on('click', '.start-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        const originalHtml = $btn.html();

        // 显示进度指示器
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.starting'));

        // 显示操作提示
        showToast('info', `正在启动服务 ${serverName}...`);

        $.ajax({
            url: `/api/servers/${serverName}/start`,
            type: 'POST',
            success: function(response) {
                showToast('success', response.message);
                // 立即刷新一次，然后延迟再刷新一次确保状态更新
                loadServersList();
                setTimeout(() => loadServersList(), 1000);
            },
            error: function(xhr) {
                let errorMsg = '启动服务器失败';
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);

                // 恢复按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);
                loadServersList();
            }
        });
    });
    
    // 验证MCP服务
    function verifyMcpServer(serverName, retry = true) {
        showToast('info', `正在获取 ${serverName} 服务的工具列表...`);
        $.ajax({
            url: `/api/servers/${serverName}/verify`,
            type: 'POST',
            success: function(response) {
                showToast('success', `服务 ${serverName} 获取工具列表成功，共有 ${response.tools.length} 个工具`);
                loadServersList();
            },
            error: function(xhr) {
                let errorMsg = `服务 ${serverName} 获取工具列表未完成，可能需要更多时间启动`;
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('warning', errorMsg);
                loadServersList();
                if (retry) {
                    setTimeout(function() {
                        verifyMcpServer(serverName, true);
                    }, 5000);
                }
            }
        });
    }
    
    // 手动验证按钮点击事件
    $(document).on('click', '.verify-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        
        // 显示加载状态
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i>');
        
        // 调用验证函数，但不进行自动重试
        verifyMcpServer(serverName, false);
        
        // 1秒后恢复按钮样式
        setTimeout(function() {
            $btn.prop('disabled', false);
            $btn.html('<i class="fas fa-list"></i> 获取列表');
        }, 1000);
    });
    
    // 停止服务器
    $(document).on('click', '.stop-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        const originalHtml = $btn.html();

        // 添加确认提示
        if (!confirm(`确定要停止服务 "${serverName}" 吗？\n\n停止后需要手动重新启动。`)) {
            return;
        }

        // 显示进度指示器
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i> 停止中...');

        // 显示操作提示
        showToast('info', `正在停止服务 ${serverName}...`);

        $.ajax({
            url: `/api/servers/${serverName}/stop`,
            type: 'POST',
            success: function(response) {
                showToast('success', response.message);
                // 立即刷新一次，然后延迟再刷新一次确保状态更新
                loadServersList();
                setTimeout(() => loadServersList(), 1000);
            },
            error: function(xhr) {
                let errorMsg = '停止服务器失败';
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);

                // 恢复按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);
                loadServersList();
            }
        });
    });
    
    // 重启服务器
    $(document).on('click', '.restart-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        const originalHtml = $btn.html();

        // 添加确认提示
        if (!confirm(`确定要重启服务 "${serverName}" 吗？\n\n重启过程中服务将暂时不可用。`)) {
            return;
        }

        // 显示进度指示器
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i> 重启中...');

        // 显示操作提示
        showToast('info', `正在重启服务 ${serverName}...`);

        $.ajax({
            url: `/api/servers/${serverName}/restart`,
            type: 'POST',
            success: function(response) {
                showToast('success', response.message);
                // 立即刷新一次，然后延迟再刷新一次确保状态更新
                loadServersList();
                setTimeout(() => loadServersList(), 1000);
            },
            error: function(xhr) {
                let errorMsg = '重启服务器失败';
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);

                // 恢复按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);
                loadServersList();
            }
        });
    });
    
    // 显示导入配置模态框
    $('#importConfigBtn').click(function() {
        // 重置表单
        $('#importConfigForm')[0].reset();
        importConfigModal.show();
    });
    
    // 提交导入配置表单
    $('#importConfigSubmitBtn').click(function() {
        const formData = new FormData($('#importConfigForm')[0]);
        
        $.ajax({
            url: '/api/import',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                importConfigModal.hide();

                // 构建详细的成功消息
                let message = response.message || '导入完成';

                // 如果有路径标准化，添加提示
                if (response.path_normalized && response.path_normalized.length > 0) {
                    message += `\n\n路径已自动标准化的服务: ${response.path_normalized.join(', ')}`;
                    message += '\n这些服务的绝对路径已转换为相对路径，提高跨平台兼容性。';
                }

                // 如果有导入的服务列表，显示详情
                if (response.imported_servers && response.imported_servers.length > 0) {
                    message += `\n\n新导入的服务: ${response.imported_servers.join(', ')}`;
                }

                showToast('success', message);
                loadServersList();
            },
            error: function(xhr) {
                let errorMsg = '导入配置失败';
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);
            }
        });
    });

    // 过滤显示相关字段
    $('#transportType').on('change', function() {
        const type = $(this).val();
        if (type === 'stdio') {
            $('#stdioFields').show();
            $('#httpFields').hide();
            $('#autoStartLabel').text('自动启动');
            $('#autoStartText').text('勾选后，系统启动时将自动启动此服务');
        } else {
            $('#stdioFields').hide();
            $('#httpFields').show();
            $('#autoStartLabel').text('自动连接');
            $('#autoStartText').text('勾选后，系统启动时将自动连接此远程服务');
        }
    });
    $('#transportType').trigger('change');

    // 编辑服务模态框类型切换
    $('#editTransportType').on('change', function() {
        const type = $(this).val();
        if (type === 'stdio') {
            $('#editStdioFields').show();
            $('#editHttpFields').hide();
            $('#editAutoStartLabel').text('自动启动');
            $('#editAutoStartText').text('勾选后，系统启动时将自动启动此服务');
        } else {
            $('#editStdioFields').hide();
            $('#editHttpFields').show();
            $('#editAutoStartLabel').text('自动连接');
            $('#editAutoStartText').text('勾选后，系统启动时将自动连接此远程服务');
        }
    });
    $('#editTransportType').trigger('change');
});

/**
 * 服务管理相关函数
 */

/**
 * 加载服务器列表
 */
function loadServersList() {

    // 清空服务器列表并显示加载状态
    const $serversList = $('#serversList');
    $serversList.html(`
        <tr>
            <td colspan="6" class="text-center">
                <div class="py-3">
                    <div class="spinner-border text-primary mb-2" role="status">
                        <span class="visually-hidden">正在加载...</span>
                    </div>
                    <p class="mb-0">正在加载 MCP 服务列表...</p>
                </div>
            </td>
        </tr>
    `);

    // 请求服务列表数据
    $.ajax({
        url: '/api/servers',
        type: 'GET',
        cache: false,
        dataType: 'json',
        success: function(response) {
            $serversList.empty();

                                // 如果没有服务，显示空消息
            if (!response || !Array.isArray(response) || response.length === 0) {
                $serversList.html(`
                    <tr>
                        <td colspan="6" class="text-center">
                            <div class="py-3">
                                <i class="fas fa-server text-muted mb-2" style="font-size: 2rem;"></i>
                                <p class="mb-0">${window.i18n.t('empty.services')}</p>
                            </div>
                        </td>
                    </tr>
                `);
                return;
            }

            // 按服务名称对服务进行排序
            response.sort((a, b) => a.name.localeCompare(b.name));

            // 添加服务到表格
            response.forEach(function(server) {
                // 根据不同服务类型获取运行状态
                let statusText = '未知';
                let statusClass = 'bg-secondary';
                let statusIcon = 'fas fa-question-circle';

                // 根据服务类型显示不同的状态描述
                if (server.transport_type === 'stdio') {
                    // stdio 类型服务状态
                    switch(server.status) {
                        case 'running':
                            statusText = window.i18n.t('status.running');
                            statusClass = 'bg-success';
                            statusIcon = 'fas fa-play-circle';
                            break;
                        case 'stopped':
                            statusText = window.i18n.t('status.stopped');
                            statusClass = 'bg-secondary';
                            statusIcon = 'fas fa-stop-circle';
                            break;
                        case 'error':
                            statusText = window.i18n.t('status.error');
                            statusClass = 'bg-danger';
                            statusIcon = 'fas fa-exclamation-circle';
                            break;
                        // 兼容已验证状态(忽略)，使其显示为运行中
                        case 'verified':
                            statusText = window.i18n.t('status.running');
                            statusClass = 'bg-success';
                            statusIcon = 'fas fa-check-circle';
                            break;
                        case 'connecting':
                            statusText = '连接中';
                            statusClass = 'bg-warning';
                            statusIcon = 'fas fa-spinner fa-spin';
                            break;
                    }
                } else {
                    // sse/streamableHTTP 类型服务状态
                    switch(server.status) {
                        case 'connected':
                            statusText = window.i18n.t('status.connected');
                            statusClass = 'bg-success';
                            statusIcon = 'fas fa-link';
                            break;
                        case 'disconnected':
                            statusText = window.i18n.t('status.stopped');
                            statusClass = 'bg-secondary';
                            statusIcon = 'fas fa-unlink';
                            break;
                        case 'error':
                            statusText = window.i18n.t('status.error');
                            statusClass = 'bg-danger';
                            statusIcon = 'fas fa-exclamation-circle';
                            break;
                        // 兼容代码，处理旧状态
                        case 'running':
                        case 'verified':
                            statusText = window.i18n.t('status.connected');
                            statusClass = 'bg-success';
                            statusIcon = 'fas fa-check-circle';
                            break;
                        case 'stopped':
                            statusText = window.i18n.t('status.stopped');
                            statusClass = 'bg-secondary';
                            statusIcon = 'fas fa-stop-circle';
                            break;
                        case 'connecting':
                            statusText = '连接中';
                            statusClass = 'bg-warning';
                            statusIcon = 'fas fa-spinner fa-spin';
                            break;
                    }
                }

                // 准备操作列按钮
                let actionsHtml = `
                    <div class="btn-group btn-group-sm">
                `;

                // 根据服务类型和状态显示不同的操作按钮
                if (server.transport_type === 'stdio') {
                    // stdio 类型服务
                    if (server.status === 'running' || server.status === 'verified') {
                        // 如果正在运行，显示停止和重启按钮
                        actionsHtml += `
                            <button class="btn btn-outline-warning btn-sm restart-server-btn" data-server="${server.name}" title="${window.i18n.t('button.restart')}">
                                <i class="fas fa-sync-alt"></i> ${window.i18n.t('button.restart')}
                            </button>
                            <button class="btn btn-outline-danger btn-sm stop-server-btn" data-server="${server.name}" title="${window.i18n.t('button.stop')}">
                                <i class="fas fa-stop"></i> ${window.i18n.t('button.stop')}
                            </button>
                        `;
                    } else if (server.status === 'stopped' || server.status === 'error') {
                        // 如果已停止或错误，显示启动按钮
                        actionsHtml += `
                            <button class="btn btn-outline-success btn-sm start-server-btn" data-server="${server.name}" title="${window.i18n.t('button.start')}">
                                <i class="fas fa-play"></i> ${window.i18n.t('button.start')}
                            </button>
                        `;
                    }
                } else {
                    // sse/streamableHTTP 类型服务
                    if (server.status === 'connected' || server.status === 'running' || server.status === 'verified') {
                        // 已连接状态，显示重启和断开连接按钮
                        actionsHtml += `
                            <button class="btn btn-outline-warning btn-sm restart-server-btn" data-server="${server.name}" title="${window.i18n.t('button.restart')}">
                                <i class="fas fa-sync-alt"></i> ${window.i18n.t('button.restart')}
                            </button>
                            <button class="btn btn-outline-danger btn-sm stop-server-btn" data-server="${server.name}" title="${window.i18n.t('button.disconnect')}">
                                <i class="fas fa-unlink"></i> ${window.i18n.t('button.disconnect')}
                            </button>
                        `;
                    } else if (server.status === 'disconnected' || server.status === 'stopped' || server.status === 'error') {
                        // 未连接状态，显示连接按钮
                        actionsHtml += `
                            <button class="btn btn-outline-success btn-sm start-server-btn" data-server="${server.name}" title="${window.i18n.t('button.start')}">
                                <i class="fas fa-link"></i> ${window.i18n.t('button.start')}
                            </button>
                        `;
                    }
                }

                // 添加编辑和删除按钮 (不论状态如何都显示)
                actionsHtml += `
                    <button class="btn btn-outline-secondary edit-server-btn" data-server="${server.name}">
                        <i class="fas fa-edit"></i> ${window.i18n.t('button.edit')}
                    </button>
                    <button class="btn btn-outline-danger delete-server-btn" data-server="${server.name}">
                        <i class="fas fa-trash"></i> ${window.i18n.t('button.delete')}
                    </button>
                `;

                actionsHtml += '</div>';

                // 建立工具模态框内容
                let toolsHtml = '';

                if (server.tools && server.tools.length > 0) {
                    const modalId = `toolsModal_${server.name.replace(/[^a-zA-Z0-9]/g, '')}`;

                    toolsHtml += `
                        <button class="btn btn-sm btn-outline-info" data-bs-toggle="modal" data-bs-target="#${modalId}">
                            <i class="fas fa-tools"></i> ${window.i18n.t('button.view.tools', {count: server.tools.length})}
                        </button>

                        <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog modal-lg">
                                <div class="modal-content">
                                    <div class="modal-header bg-secondary text-white">
                                        <h5 class="modal-title">${window.i18n.t('tools.modal.title', {name: server.name})}</h5>
                                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                    </div>
                                    <div class="modal-body">
                                        <div class="table-responsive">
                                            <table class="table table-sm table-striped">
                                                <thead>
                                                    <tr>
                                                        <th style="width: 30%">${window.i18n.t('tools.table.name')}</th>
                                                        <th>${window.i18n.t('tools.table.description')}</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                    `;

                    server.tools.forEach(tool => {
                        toolsHtml += `
                                                    <tr>
                                                        <td><code>${tool.name}</code></td>
                                                        <td>${tool.description || '<em>无描述</em>'}</td>
                                                    </tr>
                        `;
                    });

                    toolsHtml += `
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    // 根据服务类型和状态来判断是否显示获取列表按钮
                    if (server.transport_type === 'stdio' && server.status === 'running') {
                        // stdio 类型并且运行中
                        toolsHtml += `
                            <button class="btn btn-sm btn-outline-primary verify-server-btn" data-server="${server.name}">
                                <i class="fas fa-download"></i> ${window.i18n.t('button.get.tools')}
                            </button>
                        `;
                    } else if (server.transport_type !== 'stdio' && (server.status === 'connected' || server.status === 'running' || server.status === 'verified')) {
                        // sse/streamableHTTP 类型并且已连接
                        toolsHtml += `
                            <button class="btn btn-sm btn-outline-primary verify-server-btn" data-server="${server.name}">
                                <i class="fas fa-download"></i> ${window.i18n.t('button.get.tools')}
                            </button>
                        `;
                    }
                }

                // 自动启动状态
                const autoStartHtml = server.auto_start
                    ? `<span class="badge bg-success"><i class="fas fa-check"></i> ${window.i18n.t('autostart.enabled')}</span>`
                    : `<span class="badge bg-secondary"><i class="fas fa-times"></i> ${window.i18n.t('autostart.disabled')}</span>`;

                // 添加行
                $serversList.append(`
                    <tr>
                        <td>${server.name}</td>
                        <td>
                            <span class="badge rounded-pill bg-info">
                                ${server.transport_type}
                            </span>
                        </td>
                        <td>
                            <span class="badge ${statusClass} bg-opacity-75">
                                <i class="${statusIcon}"></i> ${statusText}
                            </span>
                        </td>
                        <td>${autoStartHtml}</td>
                        <td>${toolsHtml}</td>
                        <td>${actionsHtml}</td>
                    </tr>
                `);
            });
        },
        error: function(xhr, status, error) {
            console.error('加载服务列表失败:', xhr, status, error);

            // 显示错误信息并添加刷新按钮
            $('#serversList').html(`
                <tr>
                    <td colspan="6" class="text-center">
                        <div class="py-3">
                            <p class="text-danger mb-2">加载 MCP 服务列表失败</p>
                            <button class="btn btn-sm btn-primary refresh-list-btn">
                                <i class="fas fa-sync-alt me-1"></i>重新加载
                            </button>
                        </div>
                    </td>
                </tr>
            `);

            // 为刷新按钮添加点击事件
            $('.refresh-list-btn').click(function() {
                loadServersList();
            });
        }
    });
}

/**
 * 代理管理相关函数
 */

// 加载代理列表
function loadProxiesList() {
    // 检查DOM元素是否存在
    const $proxiesList = $('#proxiesList');
    
    // 清空代理列表并显示加载状态
    if ($proxiesList.length > 0) {
        $proxiesList.html(`
            <tr>
                <td colspan="9" class="text-center">
                    <div class="py-3">
                        <div class="spinner-border text-primary mb-2" role="status">
                            <span class="visually-hidden">正在加载...</span>
                        </div>
                        <p class="mb-0">正在加载 MCP 代理列表...</p>
                    </div>
                </td>
            </tr>
        `);
    }
    
    // 请求代理列表数据
    $.ajax({
        url: '/api/proxy/',
        type: 'GET',
        cache: false,
        dataType: 'json',
        success: function(response) {
            
            // 清空加载状态
            $proxiesList.empty();
            
            // 如果没有代理，显示空消息
            if (!response || !Array.isArray(response) || response.length === 0) {
                $proxiesList.html(`
                    <tr>
                        <td colspan="9" class="text-center">
                            <div class="py-3">
                                <i class="fas fa-random text-muted mb-2" style="font-size: 2rem;"></i>
                                <p class="mb-0">${window.i18n.t('empty.proxies')}</p>
                            </div>
                        </td>
                    </tr>
                `);
                return;
            }

            // 添加所有代理
            response.forEach(function(proxy, index) {
                const row = $('<tr>');
                
                // 名称列
                row.append($('<td>').text(proxy.name));
                
                // 源服务列
                row.append($('<td>').text(proxy.server_name));
                
                // 端点列
                row.append($('<td>').text(proxy.endpoint));
                
                // 类型列 - 与服务表格保持一致的样式
                row.append($('<td>').html(`
                    <span class="badge rounded-pill bg-info">
                        ${proxy.transport_type}
                    </span>
                `));
                
                // 状态列
                let statusHtml = '';
                let statusIcon = '';
                if (proxy.status === 'running') {
                    statusHtml = `<span class="badge bg-success"><i class="fas fa-play-circle"></i> ${window.i18n.t('status.running')}</span>`;
                    statusIcon = 'fas fa-play-circle';
                } else if (proxy.status === 'error') {
                    statusHtml = `<span class="badge bg-danger"><i class="fas fa-exclamation-circle"></i> ${window.i18n.t('status.error')}</span>`;
                    statusIcon = 'fas fa-exclamation-circle';
                    if (proxy.error) {
                        statusHtml += ` <small class="text-danger">${proxy.error}</small>`;
                    }
                } else {
                    statusHtml = `<span class="badge bg-secondary"><i class="fas fa-stop-circle"></i> ${window.i18n.t('status.stopped')}</span>`;
                    statusIcon = 'fas fa-stop-circle';
                }
                row.append($('<td>').html(statusHtml));

                // 自动启动列
                const autoStartHtml = proxy.auto_start
                    ? `<span class="badge bg-success"><i class="fas fa-check"></i> ${window.i18n.t('autostart.enabled')}</span>`
                    : `<span class="badge bg-secondary"><i class="fas fa-times"></i> ${window.i18n.t('autostart.disabled')}</span>`;
                row.append($('<td>').html(autoStartHtml));

                // 访问链接列 - 使用BASE URL管理器
                const fullUrl = `${BaseUrlManager.getEffectiveBaseUrl()}/${proxy.name}${proxy.endpoint}`;
                const urlHtml = `
                    <div class="d-flex align-items-center">
                        <code class="bg-light px-2 py-1 rounded text-truncate me-2" style="max-width: 200px; font-size: 0.8rem;" title="${fullUrl}">${fullUrl}</code>
                        <button class="btn btn-outline-secondary btn-sm copy-url-btn" data-url="${fullUrl}" type="button" title="复制链接">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                `;
                row.append($('<td>').html(urlHtml));
                
                // 工具列表列
                let toolsHtml = '';
                if (proxy.tools && proxy.tools.length > 0) {
                    const modalId = `proxyToolsModal_${proxy.name.replace(/[^a-zA-Z0-9]/g, '')}`;
                    
                    toolsHtml += `
                        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#${modalId}">
                            <i class="fas fa-tools"></i> ${window.i18n.t('button.view.tools', {count: proxy.tools.length})}
                        </button>
                        
                        <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog modal-lg">
                                <div class="modal-content">
                                    <div class="modal-header">
                                        <h5 class="modal-title">${window.i18n.t('tools.modal.title', {name: proxy.name})}</h5>
                                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                    </div>
                                    <div class="modal-body">
                                        <div class="table-responsive">
                                            <table class="table table-sm table-striped">
                                                <thead>
                                                    <tr>
                                                        <th>${window.i18n.t('tools.table.name')}</th>
                                                        <th>${window.i18n.t('tools.table.description')}</th>
                                                    </tr>
                                                </thead>
                                                <tbody>`;
                    
                    proxy.tools.forEach(function(tool) {
                        toolsHtml += `
                            <tr>
                                <td>${tool.name || ''}</td>
                                <td>${tool.description || ''}</td>
                            </tr>
                        `;
                    });
                    
                    toolsHtml += `
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                // 如果代理状态为运行中，添加更新工具列表按钮
                if (proxy.status === 'running') {
                    toolsHtml += `
                        <button class="btn btn-sm btn-outline-primary update-proxy-tools-btn ms-1" data-proxy="${proxy.name}" title="更新工具列表">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                    `;
                }
                
                row.append($('<td>').html(toolsHtml));
                
                // 操作列
                let actionsHtml = `<div class="btn-group btn-group-sm">`;

                // 根据代理状态显示不同的控制按钮
                if (proxy.status === 'running') {
                    // 如果正在运行，显示重启和停止按钮
                    actionsHtml += `
                        <button class="btn btn-outline-warning btn-sm restart-proxy-btn" data-proxy="${proxy.name}" title="${window.i18n.t('button.restart')}">
                            <i class="fas fa-sync-alt"></i> ${window.i18n.t('button.restart')}
                        </button>
                        <button class="btn btn-outline-danger btn-sm stop-proxy-btn" data-proxy="${proxy.name}" title="${window.i18n.t('button.stop')}">
                            <i class="fas fa-stop"></i> ${window.i18n.t('button.stop')}
                        </button>
                    `;
                } else if (proxy.status === 'stopped' || proxy.status === 'error') {
                    // 如果已停止或错误，显示启动按钮
                    actionsHtml += `
                        <button class="btn btn-outline-success btn-sm start-proxy-btn" data-proxy="${proxy.name}" title="${window.i18n.t('button.start')}">
                            <i class="fas fa-play"></i> ${window.i18n.t('button.start')}
                        </button>
                    `;
                }

                actionsHtml += `</div><div class="btn-group btn-group-sm ms-1">`;

                // 编辑按钮
                actionsHtml += `
                    <button class="btn btn-outline-secondary btn-sm edit-proxy-btn" data-proxy="${proxy.name}" title="${window.i18n.t('button.edit')}">
                        <i class="fas fa-edit"></i> ${window.i18n.t('button.edit')}
                    </button>
                `;

                // 删除按钮
                actionsHtml += `
                    <button class="btn btn-outline-danger btn-sm delete-proxy-btn" data-proxy="${proxy.name}" title="${window.i18n.t('button.delete')}">
                        <i class="fas fa-trash"></i> ${window.i18n.t('button.delete')}
                    </button>
                `;

                actionsHtml += `</div>`;

                row.append($('<td>').html(actionsHtml));
                
                // 将行添加到列表
                $proxiesList.append(row);
            });
            
            // 复制按钮事件绑定已移到文档级别，无需在此处重复绑定

            // 更新BASE URL显示
            BaseUrlManager.updateUI();
        },
        error: function(xhr, status, error) {
            console.error('获取代理列表失败:', xhr.responseText, status, error);
            console.error('状态码:', xhr.status);
            console.error('Response头:', xhr.getAllResponseHeaders());
            
            // 如果是重定向（307），尝试手动处理
            if (xhr.status === 307) {
                const redirectUrl = xhr.getResponseHeader('Location');
                if (redirectUrl) {
                    // 提取相对路径
                    const relativeUrl = redirectUrl.split('/').slice(3).join('/');

                    $.ajax({
                        url: '/' + relativeUrl,
                        type: 'GET',
                        cache: false,
                        dataType: 'json',
                        success: function(data) {
                            // 重新加载代理列表
                            loadProxiesList();
                        },
                        error: function(innerXhr, innerStatus, innerError) {
                            console.error('重定向请求失败:', innerStatus, innerError);
                            showErrorMessage();
                        }
                    });
                    return;
                }
            }
            
            // 显示标准错误信息
            showErrorMessage();
            
            function showErrorMessage() {
                // 显示错误信息并添加刷新按钮
                $proxiesList.html(`
                    <tr>
                        <td colspan="9" class="text-center">
                            <div class="py-3">
                                <p class="text-danger mb-2">加载 MCP 代理列表失败: ${xhr.status} ${xhr.statusText}</p>
                                <p>错误详情: ${error}</p>
                                <button class="btn btn-sm btn-primary refresh-proxies-list-btn">
                                    <i class="fas fa-sync-alt me-1"></i>重新加载
                                </button>
                            </div>
                        </td>
                    </tr>
                `);
                
                // 为刷新按钮添加点击事件
                $('.refresh-proxies-list-btn').click(function() {
                    loadProxiesList();
                });
            }
        }
    });
}

// 添加代理表单保存按钮
$(document).on('click', '#saveProxyBtn', function() {
    // 禁用按钮，防止重复提交
    const $btn = $(this);
    const originalHtml = $btn.html();
    $btn.prop('disabled', true);
    $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.saving'));
    
    // 获取表单数据
    const formData = {
        name: $('#proxyName').val(),
        server_name: $('#proxyServerName').val(),
        endpoint: $('#proxyEndpoint').val(),
        transport_type: $('#proxyTransportType').val(),
        exposed_tools: $('#proxyExposedTools').val().split('\n').filter(Boolean).map(s => s.trim()),
        auto_start: $('#proxyAutoStart').prop('checked')
    };
    
    // 简单验证
    if (!formData.name) {
        showToast('danger', '代理名称不能为空');
        $btn.prop('disabled', false);
        $btn.html(originalHtml);
        return;
    }
    if (!formData.server_name) {
        showToast('danger', '请选择源服务');
        $btn.prop('disabled', false);
        $btn.html(originalHtml);
        return;
    }

    // 提交表单
    $.ajax({
        url: '/api/proxy/',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function(response) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            
            // 隐藏模态框
            const addProxyModal = bootstrap.Modal.getInstance(document.getElementById('addProxyModal'));
            addProxyModal.hide();
            
            // 显示成功消息并刷新列表
            showToast('success', response.message || '添加代理成功');
            loadProxiesList();
        },
        error: function(xhr, status, error) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            
            // 显示错误信息
            console.error('添加代理失败:', xhr.responseText);
            let errorMsg = '添加代理失败';
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            } else {
                errorMsg += ': ' + error;
            }
            showToast('danger', errorMsg);
        }
    });
});

// 更新代理工具列表按钮点击事件
$(document).on('click', '.update-proxy-tools-btn', function() {
    const proxyName = $(this).data('proxy');
    const $btn = $(this);
    
    // 显示加载状态
    $btn.prop('disabled', true);
    $btn.html('<i class="fas fa-spinner fa-spin"></i>');
    
    // 调用更新工具列表API
    $.ajax({
        url: `/api/proxy/${proxyName}/update-tools`,
        type: 'POST',
        success: function(response) {
            showToast('success', `代理 ${proxyName} 工具列表更新成功，共 ${response.count} 个工具`);
            loadProxiesList();
        },
        error: function(xhr) {
            let errorMsg = `更新代理 ${proxyName} 工具列表失败`;
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);
            
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html('<i class="fas fa-sync-alt"></i>');
        }
    });
});

// 编辑代理按钮点击事件
$(document).on('click', '.edit-proxy-btn', function() {
    const proxyName = $(this).data('proxy');
    const $btn = $(this);
    
    // 显示加载状态
    $btn.prop('disabled', true);
    const originalHtml = $btn.html();
    $btn.html('<i class="fas fa-spinner fa-spin"></i>');
    
    // 获取代理信息
    $.ajax({
        url: `/api/proxy/${proxyName}`,
        type: 'GET',
        success: function(proxy) {
            // 重置按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            
            // 加载可用服务列表
            $.ajax({
                url: '/api/servers',
                type: 'GET',
                cache: false,
                dataType: 'json',
                success: function(servers) {
                    const $serverSelect = $('#editProxyServerName');
                    $serverSelect.empty();
                    
                    // 添加"请选择"选项
                    $serverSelect.append($('<option>').val('').text(window.i18n.t('dynamic.select.source')));
                    
                    // 添加可用的服务
                    if (servers && Array.isArray(servers)) {
                        servers.forEach(function(server) {
                            const option = $('<option>')
                                .val(server.name)
                                .text(server.name);
                            $serverSelect.append(option);
                        });
                    }
                    
                    // 填充表单
                    $('#editProxyName').val(proxy.name);
                    $('#editProxyOriginalName').val(proxy.name);
                    $('#editProxyServerName').val(proxy.server_name);
                    $('#editProxyEndpoint').val(proxy.endpoint);
                    $('#editProxyTransportType').val(proxy.transport_type);
                    $('#editProxyExposedTools').val((proxy.exposed_tools || []).join('\n'));
                    $('#editProxyAutoStart').prop('checked', proxy.auto_start || false);
                    
                    // 显示模态框
                    $('#editProxyModal').modal('show');
                },
                error: function(xhr) {
                    console.error('获取服务列表失败:', xhr.responseText);
                    showToast('danger', '获取可用服务列表失败，请刷新后重试');
                }
            });
        },
        error: function(xhr) {
            // 重置按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            
            let errorMsg = `获取代理 ${proxyName} 信息失败`;
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);
        }
    });
});

// 更新代理表单保存按钮
$(document).on('click', '#updateProxyBtn', function() {
    const originalName = $('#editProxyOriginalName').val();
    
    const formData = {
        name: $('#editProxyName').val(),
        server_name: $('#editProxyServerName').val(),
        endpoint: $('#editProxyEndpoint').val(),
        transport_type: $('#editProxyTransportType').val(),
        exposed_tools: $('#editProxyExposedTools').val().split('\n').filter(Boolean).map(s => s.trim()),
        auto_start: $('#editProxyAutoStart').prop('checked')
    };
    
    // 简单验证
    if (!formData.name) {
        showToast('danger', '代理名称不能为空');
        return;
    }
    if (!formData.server_name) {
        showToast('danger', '请选择源服务');
        return;
    }
    
    // 提交表单
    $.ajax({
        url: `/api/proxy/${originalName}`,
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function(response) {
            $('#editProxyModal').modal('hide');
            showToast('success', response.message || '更新代理成功');
            loadProxiesList();
        },
        error: function(xhr) {
            let errorMsg = '更新代理失败';
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);
        }
    });
});

// 删除代理按钮点击事件
$(document).on('click', '.delete-proxy-btn', function() {
    const proxyName = $(this).data('proxy');
    
    if (confirm(window.i18n.t('confirm.proxy.delete', {name: proxyName}))) {
        $.ajax({
            url: `/api/proxy/${proxyName}`,
            type: 'DELETE',
            success: function(response) {
                showToast('success', response.message || `代理 ${proxyName} 删除成功`);
                loadProxiesList();
            },
            error: function(xhr) {
                let errorMsg = `删除代理 ${proxyName} 失败`;
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);
            }
        });
    }
});

// 刷新代理列表按钮点击事件
$(document).on('click', '.refresh-proxies-list-btn', function() {
    loadProxiesList();
});

// 启动代理按钮点击事件
$(document).on('click', '.start-proxy-btn', function() {
    const proxyName = $(this).data('proxy');
    const $btn = $(this);
    const originalHtml = $btn.html();

    // 显示进度指示器
    $btn.prop('disabled', true);
    $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.starting'));

    // 显示操作提示
    showToast('info', `正在启动代理 ${proxyName}...`);

    $.ajax({
        url: `/api/proxy/${proxyName}/start`,
        type: 'POST',
        success: function(response) {
            showToast('success', response.message);
            // 立即刷新一次，然后延迟再刷新一次确保状态更新
            loadProxiesList();
            setTimeout(() => loadProxiesList(), 1000);
        },
        error: function(xhr) {
            let errorMsg = '启动代理失败';
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);

            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            loadProxiesList();
        }
    });
});

// 停止代理按钮点击事件
$(document).on('click', '.stop-proxy-btn', function() {
    const proxyName = $(this).data('proxy');
    const $btn = $(this);
    const originalHtml = $btn.html();

    // 添加确认提示
    if (!confirm(window.i18n.t('confirm.proxy.stop', {name: proxyName}))) {
        return;
    }

    // 显示进度指示器
    $btn.prop('disabled', true);
    $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.stopping'));

    // 显示操作提示
    showToast('info', `正在停止代理 ${proxyName}...`);

    $.ajax({
        url: `/api/proxy/${proxyName}/stop`,
        type: 'POST',
        success: function(response) {
            showToast('success', response.message);
            // 立即刷新一次，然后延迟再刷新一次确保状态更新
            loadProxiesList();
            setTimeout(() => loadProxiesList(), 1000);
        },
        error: function(xhr) {
            let errorMsg = '停止代理失败';
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);

            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            loadProxiesList();
        }
    });
});

// 重启代理按钮点击事件
$(document).on('click', '.restart-proxy-btn', function() {
    const proxyName = $(this).data('proxy');
    const $btn = $(this);
    const originalHtml = $btn.html();

    // 添加确认提示
    if (!confirm(`确定要重启代理 "${proxyName}" 吗？\n\n重启过程中代理将暂时不可用。`)) {
        return;
    }

    // 显示进度指示器
    $btn.prop('disabled', true);
    $btn.html('<i class="fas fa-spinner fa-spin"></i> ' + window.i18n.t('dynamic.restarting'));

    // 显示操作提示
    showToast('info', `正在重启代理 ${proxyName}...`);

    $.ajax({
        url: `/api/proxy/${proxyName}/restart`,
        type: 'POST',
        success: function(response) {
            showToast('success', response.message);
            // 立即刷新一次，然后延迟再刷新一次确保状态更新
            loadProxiesList();
            setTimeout(() => loadProxiesList(), 1000);
        },
        error: function(xhr) {
            let errorMsg = '重启代理失败';
            if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);

            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);
            loadProxiesList();
        }
    });
});

// 复制URL按钮点击事件（使用事件委托处理动态生成的按钮）
$(document).on('click', '.copy-url-btn', function(e) {
    e.preventDefault();
    e.stopPropagation();

    const $btn = $(this);
    const url = $btn.data('url');
    const urlAttr = $btn.attr('data-url');

    const finalUrl = url || urlAttr;
    if (!finalUrl) {
        console.error('URL为空，无法复制');
        showToast('danger', window.i18n.t('dynamic.copy.failed'));
        return;
    }

    // 添加视觉反馈
    const originalHtml = $btn.html();
    $btn.html('<i class="fas fa-spinner fa-spin"></i>');
    $btn.prop('disabled', true);

    // 检查浏览器是否支持 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        // 使用现代 Clipboard API
        navigator.clipboard.writeText(finalUrl)
            .then(() => {
                showToast('success', window.i18n.t('dynamic.copy.success'));
                // 恢复按钮状态
                $btn.html('<i class="fas fa-check text-success"></i>');
                setTimeout(() => {
                    $btn.html(originalHtml);
                    $btn.prop('disabled', false);
                }, 1000);
            })
            .catch(err => {
                console.error('现代API复制失败:', err);
                // 降级到传统方法
                fallbackCopyTextToClipboard(finalUrl, $btn, originalHtml);
            });
    } else {
        // 降级到传统方法
        fallbackCopyTextToClipboard(finalUrl, $btn, originalHtml);
    }
});

// 传统复制方法（兼容旧浏览器）
function fallbackCopyTextToClipboard(text, $btn, originalHtml) {

    const textArea = document.createElement("textarea");
    textArea.value = text;

    // 避免滚动到底部
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
        const successful = document.execCommand('copy');

        if (successful) {
            showToast('success', window.i18n.t('dynamic.copy.success'));
            if ($btn && originalHtml) {
                $btn.html('<i class="fas fa-check text-success"></i>');
                setTimeout(() => {
                    $btn.html(originalHtml);
                    $btn.prop('disabled', false);
                }, 1000);
            }
        } else {
            showToast('danger', window.i18n.t('dynamic.copy.failed'));
            if ($btn && originalHtml) {
                $btn.html(originalHtml);
                $btn.prop('disabled', false);
            }
        }
    } catch (err) {
        console.error('传统复制方法失败:', err);
        showToast('danger', window.i18n.t('dynamic.copy.failed'));
        if ($btn && originalHtml) {
            $btn.html(originalHtml);
            $btn.prop('disabled', false);
        }
    }

    document.body.removeChild(textArea);
}

/**
 * 通用复制函数
 */
function copyToClipboard(text) {
    // 检查浏览器是否支持 Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        // 使用现代 Clipboard API
        navigator.clipboard.writeText(text)
            .then(() => {
                showToast('success', window.i18n.t('dynamic.copy.success'));
            })
            .catch(err => {
                console.error('现代API复制失败:', err);
                // 降级到传统方法
                fallbackCopyTextToClipboard(text);
            });
    } else {
        // 降级到传统方法
        fallbackCopyTextToClipboard(text);
    }
}



// 页面加载完成后的初始化

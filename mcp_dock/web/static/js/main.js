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

            // 保存当前活动的 tab 状态
            TabStateManager.saveActiveTab(target);

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

// 全局缓存，存储服务器的完整工具列表
window.serverToolsCache = window.serverToolsCache || {};

// Tab 状态管理
const TabStateManager = {
    // 本地存储键名
    STORAGE_KEY: 'mcp_dock_active_tab',

    // 保存当前活动的 tab
    saveActiveTab: function(tabId) {
        try {
            localStorage.setItem(this.STORAGE_KEY, tabId);
        } catch (e) {
            console.warn('保存 tab 状态失败:', e);
        }
    },

    // 获取保存的活动 tab
    getActiveTab: function() {
        try {
            return localStorage.getItem(this.STORAGE_KEY);
        } catch (e) {
            console.warn('获取 tab 状态失败:', e);
            return null;
        }
    },

    // 恢复 tab 状态
    restoreTabState: function() {
        const savedTab = this.getActiveTab();
        if (savedTab) {
            // 查找对应的导航链接
            const $navLink = $(`#sidebar .nav-link[data-bs-target="${savedTab}"]`);
            if ($navLink.length > 0) {
                // 如果有预设状态，说明初始状态已经正确设置，只需要加载数据
                if (window.mcpDockPresetTab === savedTab) {
                    // 直接加载对应的数据，不触发点击事件
                    if (savedTab === '#serversTab') {
                        loadServersList();
                    } else if (savedTab === '#proxiesTab') {
                        loadProxiesList();
                    }
                } else {
                    // 没有预设状态或预设状态不匹配，触发点击事件
                    $navLink.trigger('click');
                }
                return true;
            }
        }
        return false;
    }
};

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
    function initializeI18n() {
        if (typeof window.i18n !== 'undefined') {
            // 应用国际化翻译
            window.i18n.applyTranslations();

            // 为动态内容添加翻译支持
            window.translateDynamicContent = function() {
                if (typeof window.i18n !== 'undefined') {
                    window.i18n.applyTranslations();
                }
            };
            return true;
        }
        return false;
    }

    // 尝试初始化，如果失败则等待一下再试
    if (!initializeI18n()) {
        setTimeout(initializeI18n, 100);
    }

    // 初始化侧边栏
    SidebarManager.init();

    // 初始化BASE URL配置
    BaseUrlManager.loadFromStorage();
    BaseUrlManager.updateUI();

    // 恢复 tab 状态
    if (!TabStateManager.restoreTabState()) {
        // 如果没有保存的状态或恢复失败，默认显示服务器页面
        // 但是不触发点击事件，因为初始状态已经在 HTML 中设置好了
        if (!window.mcpDockPresetTab) {
            $('#sidebar .nav-link[data-bs-target="#serversTab"]').trigger('click');
        }
    }

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

    // 注意：服务器列表和代理列表现在由 tab 状态管理器根据活动页面来加载
    
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

        // 隐藏服务信息和工具选择部分
        $('#proxyServiceInfo').hide();
        $('#proxyToolsSelection').hide();

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

    // 添加代理模态框中的服务选择变化事件
    $('#proxyServerName').on('change', function() {
        const selectedServer = $(this).val();
        if (selectedServer) {
            loadServerInfoForProxy(selectedServer, 'add');
        } else {
            $('#proxyServiceInfo').hide();
            $('#proxyToolsSelection').hide();
        }
    });

    // 编辑代理模态框中的服务选择变化事件
    $('#editProxyServerName').on('change', function() {
        const selectedServer = $(this).val();
        if (selectedServer) {
            loadServerInfoForProxy(selectedServer, 'edit');
        } else {
            $('#editProxyServiceInfo').hide();
            $('#editProxyToolsSelection').hide();
        }
    });

    // 用法说明编辑按钮事件
    $('#editAddInstructionsBtn').on('click', function() {
        const $input = $('#proxyInstructions');
        $input.prop('readonly', false);
        $input.focus();
        $(this).text(window.i18n.t('action.save')).removeClass('btn-outline-primary').addClass('btn-primary');
    });

    $('#editInstructionsBtn').on('click', function() {
        const $input = $('#editProxyInstructions');
        $input.prop('readonly', false);
        $input.focus();
        $(this).text(window.i18n.t('action.save')).removeClass('btn-outline-primary').addClass('btn-primary');
    });

    // 恢复默认用法说明按钮事件
    $('#resetAddInstructionsBtn').on('click', function() {
        const serverName = $('#proxyServerName').val();
        if (serverName) {
            // 获取服务器的原始用法说明
            $.ajax({
                url: `/api/servers/${serverName}`,
                type: 'GET',
                success: function(server) {
                    let originalInstructions = "No Instructions";
                    if (server.server_info && (server.server_info.instructions || server.server_info.description)) {
                        originalInstructions = server.server_info.instructions || server.server_info.description;
                    } else if (server.instructions && server.instructions !== `MCP 服务 ${server.name}`) {
                        originalInstructions = server.instructions;
                    }

                    // Instructions 字段始终显示，设置相应的值
                    $('#proxyServiceInfo').show();
                    if (originalInstructions === "No Instructions" || !originalInstructions.trim()) {
                        $('#proxyInstructions').val('');
                    } else {
                        $('#proxyInstructions').val(originalInstructions);
                    }
                    $('#editAddInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
                    $('#proxyInstructions').prop('readonly', true);
                },
                error: function() {
                    // Instructions 字段始终显示，错误时设置为空
                    $('#proxyServiceInfo').show();
                    $('#proxyInstructions').val('');
                    $('#editAddInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
                    $('#proxyInstructions').prop('readonly', true);
                }
            });
        }
    });

    $('#resetInstructionsBtn').on('click', function() {
        const serverName = $('#editProxyServerName').val();
        if (serverName) {
            // 获取服务器的原始用法说明
            $.ajax({
                url: `/api/servers/${serverName}`,
                type: 'GET',
                success: function(server) {
                    let originalInstructions = "No Instructions";
                    if (server.server_info && (server.server_info.instructions || server.server_info.description)) {
                        originalInstructions = server.server_info.instructions || server.server_info.description;
                    }
                    // 注意：不再使用 server.instructions，因为它可能包含中文模板描述

                    // Instructions 字段始终显示，设置相应的值
                    $('#editProxyServiceInfo').show();
                    if (originalInstructions === "No Instructions" || !originalInstructions.trim()) {
                        $('#editProxyInstructions').val('');
                    } else {
                        $('#editProxyInstructions').val(originalInstructions);
                    }
                    $('#editInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
                    $('#editProxyInstructions').prop('readonly', true);
                },
                error: function() {
                    // Instructions 字段始终显示，错误时设置为空
                    $('#editProxyServiceInfo').show();
                    $('#editProxyInstructions').val('');
                    $('#editInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
                    $('#editProxyInstructions').prop('readonly', true);
                }
            });
        }
    });

    // 工具全选/全不选按钮事件
    $('#selectAllAddToolsBtn').on('click', function() {
        $('#proxyToolsList .tool-checkbox').prop('checked', true);
        $('#proxyToolsList .tool-checkbox').each(function() {
            updateToolAppearance($(this));
        });
        updateSelectedToolsList('add');
    });

    $('#deselectAllAddToolsBtn').on('click', function() {
        $('#proxyToolsList .tool-checkbox').prop('checked', false);
        $('#proxyToolsList .tool-checkbox').each(function() {
            updateToolAppearance($(this));
        });
        updateSelectedToolsList('add');
    });

    $('#selectAllToolsBtn').on('click', function() {
        $('#editProxyToolsList .tool-checkbox').prop('checked', true);
        $('#editProxyToolsList .tool-checkbox').each(function() {
            updateToolAppearance($(this));
        });
        updateSelectedToolsList('edit');
    });

    $('#deselectAllToolsBtn').on('click', function() {
        $('#editProxyToolsList .tool-checkbox').prop('checked', false);
        $('#editProxyToolsList .tool-checkbox').each(function() {
            updateToolAppearance($(this));
        });
        updateSelectedToolsList('edit');
    });

    // 保存按钮处理
    $('#saveServerBtn').off('click').on('click', function() {
        const type = $('#transportType').val();
        const formData = new FormData();
        formData.append('name', $('#serverName').val());
        formData.append('transport_type', type);
        
        // 处理自动启动/连接选项(适用于所有服务类型)
        formData.append('auto_start', $('#autoStart').prop('checked'));

        // 添加空的 instructions 字段（服务级别不编辑 instructions）
        formData.append('instructions', '');

        if (type === 'stdio') {
            formData.append('command', $('#command').val());

            // 参数 - 统一使用 JSON 格式处理
            const argsText = $('#args').val().trim();
            let argsArray = [];
            if (argsText) {
                try {
                    argsArray = JSON.parse(argsText);
                    if (!Array.isArray(argsArray)) {
                        throw new Error('参数必须是数组格式');
                    }
                } catch (e) {
                    showToast('danger', '参数格式错误: ' + e.message);
                    return;
                }
            }
            formData.append('args', JSON.stringify(argsArray));

            // 环境变量 - 统一使用 JSON 格式处理
            const envText = $('#env').val().trim();
            let envObj = {};
            if (envText) {
                try {
                    envObj = JSON.parse(envText);
                    if (typeof envObj !== 'object' || Array.isArray(envObj)) {
                        throw new Error('环境变量必须是对象格式');
                    }
                } catch (e) {
                    showToast('danger', '环境变量格式错误: ' + e.message);
                    return;
                }
            }
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
                let errorMsg = window.i18n.t('error.service.add');
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
            // 验证参数字段 JSON 格式
            const argsText = $('#editArgs').val().trim();
            if (argsText) {
                try {
                    const argsArray = JSON.parse(argsText);
                    if (!Array.isArray(argsArray)) {
                        throw new Error('参数必须是数组格式');
                    }
                } catch(e) {
                    showToast('danger', '参数格式错误: ' + e.message);
                    $btn.prop('disabled', false);
                    $btn.html(originalHtml);
                    return;
                }
            }

            // 验证环境变量字段 JSON 格式
            const envText = $('#editEnv').val().trim();
            if (envText) {
                try {
                    const envObj = JSON.parse(envText);
                    if (typeof envObj !== 'object' || Array.isArray(envObj)) {
                        throw new Error('环境变量必须是对象格式');
                    }
                } catch(e) {
                    showToast('danger', '环境变量格式错误: ' + e.message);
                    $btn.prop('disabled', false);
                    $btn.html(originalHtml);
                    return;
                }
            }
        
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
                    let errorMsg = window.i18n.t('error.service.delete');
                    if (xhr.responseJSON && xhr.responseJSON.detail) {
                        errorMsg += ': ' + xhr.responseJSON.detail;
                    }
                    showToast('danger', errorMsg);
                    $btn.prop('disabled', false);
                    $btn.html(`<i class="fas fa-trash"></i> ${window.i18n.t('button.delete')}`);
                    loadServersList();
                }
            });
        } else {
            $btn.prop('disabled', false);
            $btn.html(`<i class="fas fa-trash"></i> ${window.i18n.t('button.delete')}`);
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

    // 添加服务模态框测试按钮点击事件
    $('#testAddServerBtn').click(function() {
        testServerInModal('add');
    });

    // 编辑服务模态框测试按钮点击事件
    $('#testEditServerBtn').click(function() {
        testServerInModal('edit');
    });

    // 测试服务按钮点击事件（表格中的测试按钮，保留用于兼容性）
    $(document).on('click', '.test-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        const originalHtml = $btn.html();

        // 显示加载状态
        $btn.prop('disabled', true);
        $btn.html('<i class="fas fa-spinner fa-spin"></i> 测试中...');

        // 调用测试API
        $.ajax({
            url: `/api/servers/${serverName}/test`,
            type: 'POST',
            success: function(response) {
                // 恢复按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);

                // 显示测试结果
                showTestResult(response.server_info);
                showToast('success', response.message);
            },
            error: function(xhr) {
                // 恢复按钮状态
                $btn.prop('disabled', false);
                $btn.html(originalHtml);

                let errorMsg = `测试服务 ${serverName} 失败`;
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    errorMsg = xhr.responseJSON.message;
                } else if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg += ': ' + xhr.responseJSON.detail;
                }
                showToast('danger', errorMsg);
            }
        });
    });
    
    // 停止服务器
    $(document).on('click', '.stop-server-btn', function() {
        const serverName = $(this).data('server');
        const $btn = $(this);
        const originalHtml = $btn.html();

        // 添加确认提示
        if (!confirm(window.i18n.t('confirm.service.stop', {name: serverName}))) {
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
        if (!confirm(window.i18n.t('confirm.service.restart', {name: serverName}))) {
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
        updateTestButtonVisibility('add');
    });
    $('#transportType').trigger('change');

    // 监听表单字段变化以更新测试按钮可见性
    $('#serverName, #command, #url').on('input', function() {
        updateTestButtonVisibility('add');
    });

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
        updateTestButtonVisibility('edit');
    });
    $('#editTransportType').trigger('change');

    // 监听编辑表单字段变化以更新测试按钮可见性
    $('#editServerName, #editCommand, #editUrl').on('input', function() {
        updateTestButtonVisibility('edit');
    });

    // 模态框显示时初始化测试按钮
    $('#addServerModal').on('shown.bs.modal', function() {
        updateTestButtonVisibility('add');
        // 确保国际化翻译被应用
        if (typeof window.i18n !== 'undefined') {
            window.i18n.applyTranslations();
        }
    });

    $('#editServerModal').on('shown.bs.modal', function() {
        updateTestButtonVisibility('edit');
        // 确保国际化翻译被应用
        if (typeof window.i18n !== 'undefined') {
            window.i18n.applyTranslations();
        }
    });

    // 模态框隐藏时重置测试结果
    $('#addServerModal').on('hidden.bs.modal', function() {
        $('#addServerTestResult').hide();
        $('#addServerTestContent').empty();
    });

    $('#editServerModal').on('hidden.bs.modal', function() {
        $('#editServerTestResult').hide();
        $('#editServerTestContent').empty();
    });


});

/**
 * 更新测试按钮状态和验证
 */
function updateTestButtonVisibility(mode) {
    const isEdit = mode === 'edit';

    // 构建正确的字段 ID
    const nameField = isEdit ? '#editServerName' : '#serverName';
    const transportField = isEdit ? '#editTransportType' : '#transportType';
    const commandField = isEdit ? '#editCommand' : '#command';
    const urlField = isEdit ? '#editUrl' : '#url';

    const name = $(nameField).val();
    const transportType = $(transportField).val();

    const $testBtn = $(`#test${isEdit ? 'Edit' : 'Add'}ServerBtn`);

    // 总是显示测试按钮
    $testBtn.show();

    // 验证逻辑
    const validation = validateTestFields(name, transportType, $(commandField).val(), $(urlField).val());

    if (validation.isValid) {
        $testBtn.prop('disabled', false);
        $testBtn.attr('title', '');
        $testBtn.find('i').removeClass('fa-exclamation-triangle').addClass('fa-vial');
    } else {
        $testBtn.prop('disabled', true);
        $testBtn.attr('title', validation.message);
        $testBtn.find('i').removeClass('fa-vial').addClass('fa-exclamation-triangle');
    }
}

/**
 * 验证测试字段
 */
function validateTestFields(name, transportType, command, url) {
    if (!name || name.trim() === '') {
        return { isValid: false, message: window.i18n.t('test.validation.name.required') };
    }

    if (!transportType) {
        return { isValid: false, message: window.i18n.t('test.validation.type.required') };
    }

    if (transportType === 'stdio') {
        if (!command || command.trim() === '') {
            return { isValid: false, message: window.i18n.t('test.validation.command.required') };
        }
    } else {
        if (!url || url.trim() === '') {
            return { isValid: false, message: window.i18n.t('test.validation.url.required') };
        }

        // 简单的 URL 验证
        try {
            new URL(url);
        } catch (e) {
            return { isValid: false, message: window.i18n.t('test.validation.url.invalid') };
        }
    }

    return { isValid: true, message: '' };
}

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

    // 首先获取所有服务器信息以缓存工具列表
    $.ajax({
        url: '/api/servers',
        type: 'GET',
        cache: false,
        dataType: 'json',
        success: function(servers) {
            // 缓存服务器工具信息
            if (servers && Array.isArray(servers)) {
                servers.forEach(function(server) {
                    if (server.tools && Array.isArray(server.tools)) {
                        window.serverToolsCache[server.name] = server.tools;
                    }
                });
            }

            // 然后加载代理列表
            loadProxiesListWithCache();
        },
        error: function() {
            // 即使获取服务器信息失败，也继续加载代理列表
            loadProxiesListWithCache();
        }
    });
}

// 使用缓存的服务器信息加载代理列表
function loadProxiesListWithCache() {
    const $proxiesList = $('#proxiesList');

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

                    // 计算启用和总工具数
                    // 从缓存的源服务信息中获取完整工具列表
                    const serverTools = window.serverToolsCache && window.serverToolsCache[proxy.server_name]
                        ? window.serverToolsCache[proxy.server_name]
                        : proxy.tools; // 回退到当前工具列表

                    const totalTools = serverTools.length;

                    let enabledTools;
                    if (!proxy.exposed_tools || proxy.exposed_tools.length === 0) {
                        // 没有设置过滤，所有工具都启用
                        enabledTools = totalTools;
                    } else {
                        // 设置了过滤，计算有多少工具在 exposed_tools 列表中
                        enabledTools = serverTools.filter(tool =>
                            proxy.exposed_tools.includes(tool.name)
                        ).length;
                    }

                    toolsHtml += `
                        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#${modalId}">
                            <i class="fas fa-tools"></i> ${window.i18n.t('button.view.tools.detailed', {enabled: enabledTools, total: totalTools})}
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
                    
                    // 显示所有工具（从缓存的完整工具列表）
                    serverTools.forEach(function(tool) {
                        // 检查工具是否在代理的暴露工具列表中
                        // 如果没有设置 exposed_tools 或为空数组，则所有工具都启用
                        // 如果设置了 exposed_tools，则只有在列表中的工具才启用
                        const isExposed = (!proxy.exposed_tools || proxy.exposed_tools.length === 0)
                            ? true
                            : proxy.exposed_tools.includes(tool.name);
                        const statusBadge = isExposed
                            ? `<span class="badge bg-success ms-2">${window.i18n.t('status.enabled')}</span>`
                            : `<span class="badge bg-secondary ms-2">${window.i18n.t('status.disabled')}</span>`;

                        toolsHtml += `
                            <tr>
                                <td>${tool.name || ''}${statusBadge}</td>
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
    const exposedToolsValue = $('#proxyExposedTools').val() || '';
    const formData = {
        name: $('#proxyName').val(),
        server_name: $('#proxyServerName').val(),
        endpoint: $('#proxyEndpoint').val(),
        transport_type: $('#proxyTransportType').val(),
        exposed_tools: exposedToolsValue ? exposedToolsValue.split('\n').filter(Boolean).map(s => s.trim()) : [],
        auto_start: $('#proxyAutoStart').prop('checked'),
        instructions: $('#proxyInstructions').val() || ""
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
            showToast('success', response.message || window.i18n.t('success.proxy.added'));
            loadProxiesList();
        },
        error: function(xhr, status, error) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);

            // 显示错误信息
            console.error('添加代理失败:', xhr.responseText);
            let errorMsg = window.i18n.t('error.proxy.add');
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
            showToast('success', window.i18n.t('success.proxy.tools.updated', {name: proxyName, count: response.count}));
            loadProxiesList();
        },
        error: function(xhr) {
            let errorMsg = window.i18n.t('error.proxy.tools.update', {name: proxyName});
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

                    // 如果选择了服务，加载服务信息（这会设置正确的描述）
                    if (proxy.server_name) {
                        loadServerInfoForProxy(proxy.server_name, 'edit', proxy.exposed_tools || []);
                    } else {
                        // 如果没有选择服务，使用代理配置中的用法说明
                        const instructions = proxy.instructions || "No Instructions";
                        $('#editProxyInstructions').val(instructions);
                    }
                    
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
    
    const editExposedToolsValue = $('#editProxyExposedTools').val() || '';
    const formData = {
        name: $('#editProxyName').val(),
        server_name: $('#editProxyServerName').val(),
        endpoint: $('#editProxyEndpoint').val(),
        transport_type: $('#editProxyTransportType').val(),
        exposed_tools: editExposedToolsValue ? editExposedToolsValue.split('\n').filter(Boolean).map(s => s.trim()) : [],
        auto_start: $('#editProxyAutoStart').prop('checked'),
        instructions: $('#editProxyInstructions').val() || ""
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
            showToast('success', response.message || window.i18n.t('success.proxy.updated'));
            loadProxiesList();
        },
        error: function(xhr) {
            let errorMsg = window.i18n.t('error.proxy.update');
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
                showToast('success', response.message || window.i18n.t('success.proxy.deleted', {name: proxyName}));
                loadProxiesList();
            },
            error: function(xhr) {
                let errorMsg = window.i18n.t('error.proxy.delete', {name: proxyName});
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
    if (!confirm(window.i18n.t('confirm.proxy.restart', {name: proxyName}))) {
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
 * 加载服务信息用于代理配置
 */
function loadServerInfoForProxy(serverName, mode, selectedTools = []) {
    // 显示加载状态
    const loadingHtml = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> 正在加载服务信息...</div>';

    if (mode === 'add') {
        $('#proxyServiceInfo').show();
        $('#proxyToolsSelection').show();
        $('#proxyToolsList').html(loadingHtml);
    } else {
        $('#editProxyServiceInfo').show();
        $('#editProxyToolsSelection').show();
        $('#editProxyToolsList').html(loadingHtml);
    }

    // 获取服务信息
    $.ajax({
        url: `/api/servers/${serverName}`,
        type: 'GET',
        success: function(server) {
            // 获取服务器的原始用法说明，只使用 server_info 中的说明
            let originalInstructions = "No Instructions";
            if (server.server_info && (server.server_info.instructions || server.server_info.description)) {
                originalInstructions = server.server_info.instructions || server.server_info.description;
            }
            // 注意：不再使用 server.instructions，因为它可能包含中文模板描述

            // Instructions 字段始终显示，不论内容是否为空
            if (mode === 'add') {
                $('#proxyServiceInfo').show();
                // 设置 instructions 值：如果为空或"No Instructions"，则显示空字符串
                if (originalInstructions === "No Instructions" || !originalInstructions.trim()) {
                    $('#proxyInstructions').val('');
                } else {
                    $('#proxyInstructions').val(originalInstructions);
                }
                $('#proxyInstructions').prop('readonly', true);
                $('#editAddInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
            } else {
                $('#editProxyServiceInfo').show();
                // 在编辑模式下，检查当前用法说明是否已被用户自定义
                const currentInstructions = $('#editProxyInstructions').val();
                // 如果当前用法说明为空、是默认模板或者是"No Instructions"，则使用原始说明
                if (!currentInstructions ||
                    currentInstructions.startsWith('MCP 服务') ||
                    currentInstructions === 'No Instructions') {
                    // 设置原始说明：如果为空或"No Instructions"，则显示空字符串
                    if (originalInstructions === "No Instructions" || !originalInstructions.trim()) {
                        $('#editProxyInstructions').val('');
                    } else {
                        $('#editProxyInstructions').val(originalInstructions);
                    }
                }
                $('#editProxyInstructions').prop('readonly', true);
                $('#editInstructionsBtn').text(window.i18n.t('action.edit.instructions')).removeClass('btn-primary').addClass('btn-outline-primary');
            }

            // 显示工具列表
            displayToolsForSelection(server.tools || [], mode, selectedTools);
        },
        error: function(xhr) {
            console.error('获取服务信息失败:', xhr.responseText);
            showToast('danger', window.i18n.t('error.service.info.load'));

            // Instructions 字段始终显示，错误时设置为空
            if (mode === 'add') {
                $('#proxyServiceInfo').show();
                $('#proxyInstructions').val('');
                $('#proxyToolsSelection').hide();
            } else {
                $('#editProxyServiceInfo').show();
                $('#editProxyInstructions').val('');
                $('#editProxyToolsSelection').hide();
            }
        }
    });
}

/**
 * 显示工具选择列表
 */
function displayToolsForSelection(tools, mode, selectedTools = []) {
    const containerId = mode === 'add' ? '#proxyToolsList' : '#editProxyToolsList';
    const $container = $(containerId);

    if (!tools || tools.length === 0) {
        $container.html(`<div class="text-muted text-center py-3">${window.i18n.t('test.results.no.tools')}</div>`);
        return;
    }

    let toolsHtml = '';
    tools.forEach((tool, index) => {
        const toolId = `${mode}Tool${index}`;
        // 检查工具是否在选中列表中（编辑模式时使用已保存的选择，添加模式时默认全选）
        const isSelected = mode === 'edit' ? selectedTools.includes(tool.name) : true;
        const badgeClass = isSelected ? 'selected' : 'unselected';

        toolsHtml += `
            <div class="tool-item d-inline-block" data-tool-name="${tool.name}">
                <input class="tool-checkbox" type="checkbox" value="${tool.name}" id="${toolId}" ${isSelected ? 'checked' : ''} style="display: none;">
                <div class="tool-badge ${badgeClass}" data-tool="${tool.name}">
                    <i class="fas fa-cog"></i>
                    <span>${tool.name}</span>
                </div>
            </div>
        `;
    });

    $container.html(toolsHtml);

    // 绑定工具标签点击事件
    $container.find('.tool-badge').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();

        const $badge = $(this);
        const $toolItem = $badge.closest('.tool-item');
        const $checkbox = $toolItem.find('.tool-checkbox');

        // 切换复选框状态
        $checkbox.prop('checked', !$checkbox.is(':checked'));

        // 更新外观和列表
        updateToolAppearance($checkbox);
        updateSelectedToolsList(mode);
    });

    // 绑定复选框变化事件（用于全选/全不选按钮）
    $container.find('.tool-checkbox').on('change', function() {
        updateToolAppearance($(this));
        updateSelectedToolsList(mode);
    });

    // 初始更新选中的工具列表
    updateSelectedToolsList(mode);
}

/**
 * 更新工具外观（选中/未选中状态）
 */
function updateToolAppearance($checkbox) {
    const $toolItem = $checkbox.closest('.tool-item');
    const $badge = $toolItem.find('.tool-badge');

    if ($checkbox.is(':checked')) {
        $badge.removeClass('unselected').addClass('selected');
    } else {
        $badge.removeClass('selected').addClass('unselected');
    }
}

/**
 * 更新选中的工具列表（存储在隐藏字段中）
 */
function updateSelectedToolsList(mode) {
    const containerId = mode === 'add' ? '#proxyToolsList' : '#editProxyToolsList';

    const selectedTools = [];
    $(containerId + ' .tool-checkbox:checked').each(function() {
        selectedTools.push($(this).val());
    });

    // 将选中的工具存储在隐藏字段中，用于表单提交
    const hiddenFieldId = mode === 'add' ? '#proxyExposedTools' : '#editProxyExposedTools';
    $(hiddenFieldId).val(selectedTools.join('\n'));
}

/**
 * 在模态框中测试服务
 */
function testServerInModal(mode) {
    const isEdit = mode === 'edit';
    const prefix = isEdit ? 'edit' : 'add';

    // 获取表单数据
    const formData = getServerFormData(mode);
    if (!formData) {
        showToast('warning', window.i18n.t('error.form.incomplete'));
        return;
    }

    const $btn = $(`#test${isEdit ? 'Edit' : 'Add'}ServerBtn`);
    const originalHtml = $btn.html();

    // 显示加载状态
    $btn.prop('disabled', true);
    $btn.html(`<i class="fas fa-spinner fa-spin"></i> ${window.i18n.t('test.button.testing')}`);

    // 如果是编辑模式，使用现有服务名称进行测试
    let testUrl;
    if (isEdit) {
        const serverName = $('#editServerOriginalName').val();
        testUrl = `/api/servers/${serverName}/test`;
    } else {
        // 添加模式，需要创建临时配置进行测试
        testUrl = '/api/servers/test-config';
    }

    // 调用测试API
    $.ajax({
        url: testUrl,
        type: 'POST',
        data: isEdit ? undefined : JSON.stringify(formData),
        contentType: isEdit ? undefined : 'application/json',
        success: function(response) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);

            // 在模态框内显示测试结果
            showTestResultInModal(response.server_info, mode);
            showToast('success', response.message);
        },
        error: function(xhr) {
            // 恢复按钮状态
            $btn.prop('disabled', false);
            $btn.html(originalHtml);

            let errorMsg = window.i18n.t('error.service.test');
            if (xhr.responseJSON && xhr.responseJSON.message) {
                errorMsg = xhr.responseJSON.message;
            } else if (xhr.responseJSON && xhr.responseJSON.detail) {
                errorMsg += ': ' + xhr.responseJSON.detail;
            }
            showToast('danger', errorMsg);
        }
    });
}

/**
 * 获取服务表单数据
 */
function getServerFormData(mode) {
    const isEdit = mode === 'edit';
    const prefix = isEdit ? 'edit' : '';

    const name = $(`#${prefix}${prefix ? 'S' : 's'}erverName`).val();
    const transportType = $(`#${prefix}${prefix ? 'T' : 't'}ransportType`).val();

    if (!name || !transportType) {
        return null;
    }

    const formData = {
        name: name,
        transport_type: transportType,
        auto_start: false // 测试时不需要自动启动
    };

    if (transportType === 'stdio') {
        const command = $(`#${prefix}${prefix ? 'C' : 'c'}ommand`).val();
        const args = $(`#${prefix}${prefix ? 'A' : 'a'}rgs`).val();
        const env = $(`#${prefix}${prefix ? 'E' : 'e'}nv`).val();

        if (!command) {
            return null;
        }

        formData.command = command;

        // 处理参数
        if (args) {
            if (isEdit) {
                // 编辑模式，args是JSON格式
                try {
                    formData.args = JSON.parse(args);
                } catch (e) {
                    formData.args = [];
                }
            } else {
                // 添加模式，args是每行一个参数
                formData.args = args.split('\n').filter(arg => arg.trim());
            }
        } else {
            formData.args = [];
        }

        // 处理环境变量
        if (env) {
            if (isEdit) {
                // 编辑模式，env是JSON格式
                try {
                    formData.env = JSON.parse(env);
                } catch (e) {
                    formData.env = {};
                }
            } else {
                // 添加模式，env是每行KEY=VALUE格式
                formData.env = {};
                env.split('\n').forEach(line => {
                    const [key, ...valueParts] = line.split('=');
                    if (key && valueParts.length > 0) {
                        formData.env[key.trim()] = valueParts.join('=').trim();
                    }
                });
            }
        } else {
            formData.env = {};
        }
    } else {
        const url = $(`#${prefix}${prefix ? 'U' : 'u'}rl`).val();
        if (!url) {
            return null;
        }
        formData.url = url;
    }

    return formData;
}

/**
 * 在模态框内显示测试结果
 */
function showTestResultInModal(serverInfo, mode) {
    const prefix = mode === 'edit' ? 'edit' : 'add';
    const $resultArea = $(`#${prefix}ServerTestResult`);
    const $content = $(`#${prefix}ServerTestContent`);

    // 构建测试结果内容
    let contentHtml = `
        <!-- 基本信息部分 -->
        <div class="test-result-section">
            <div class="test-result-header">
                <i class="fas fa-info-circle text-primary"></i>
                <h6 class="mb-0 text-primary">${window.i18n.t('test.results.basic.info')}</h6>
            </div>
            <div class="row">
                <div class="col-md-4">
                    <div class="d-flex align-items-center mb-2">
                        <strong class="me-2">${window.i18n.t('test.results.service.name')}:</strong>
                        <span class="badge bg-primary">${serverInfo.name}</span>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="d-flex align-items-center mb-2">
                        <strong class="me-2">${window.i18n.t('test.results.transport.type')}:</strong>
                        <span class="badge bg-info">${serverInfo.transport_type}</span>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="d-flex align-items-center mb-2">
                        <strong class="me-2">${window.i18n.t('test.results.status')}:</strong>
                        <span class="badge bg-success">${serverInfo.status}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 服务用法说明部分 -->
        <div class="test-result-section">
            <div class="test-result-header">
                <i class="fas fa-file-alt text-info"></i>
                <h6 class="mb-0 text-info">${window.i18n.t('test.results.instructions')}</h6>
            </div>
            <div class="test-result-instructions">
                <div class="instructions-text">
                    ${serverInfo.instructions || serverInfo.description || `<em class="text-muted">No Instructions</em>`}
                </div>
            </div>
        </div>

        <!-- 工具列表部分 -->
        <div class="test-result-section">
            <div class="test-result-header">
                <i class="fas fa-tools text-success"></i>
                <h6 class="mb-0 text-success">${window.i18n.t('test.results.tools.count', {count: serverInfo.tools.length})}</h6>
            </div>
            <div class="test-result-tools-container">
    `;

    if (serverInfo.tools && serverInfo.tools.length > 0) {
        contentHtml += '<div class="test-result-tools-grid">';

        serverInfo.tools.forEach(tool => {
            contentHtml += `
                <div class="test-result-tool-badge">
                    <i class="fas fa-cog"></i>
                    <span>${tool.name || window.i18n.t('tool.unknown')}</span>
                </div>
            `;
        });

        contentHtml += '</div>';
    } else {
        contentHtml += `
            <div class="test-result-no-tools">
                <i class="fas fa-tools"></i>
                <p class="mb-0">${window.i18n.t('test.results.no.tools')}</p>
            </div>
        `;
    }

    contentHtml += `
            </div>
        </div>
    `;

    $content.html(contentHtml);
    $resultArea.show();
}

/**
 * 显示测试结果模态框（保留用于兼容性）
 */
function showTestResult(serverInfo) {
    const $content = $('#testResultContent');

    // 构建测试结果内容
    let contentHtml = `
        <div class="row">
            <div class="col-md-6">
                <h6 class="text-primary">基本信息</h6>
                <table class="table table-sm">
                    <tr>
                        <td><strong>服务名称:</strong></td>
                        <td>${serverInfo.name}</td>
                    </tr>
                    <tr>
                        <td><strong>传输类型:</strong></td>
                        <td><span class="badge bg-info">${serverInfo.transport_type}</span></td>
                    </tr>
                    <tr>
                        <td><strong>状态:</strong></td>
                        <td><span class="badge bg-success">${serverInfo.status}</span></td>
                    </tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6 class="text-primary">服务描述</h6>
                <div class="border rounded p-2 bg-light">
                    <p class="mb-0">${serverInfo.description || '<em class="text-muted">无描述</em>'}</p>
                </div>
            </div>
        </div>

        <div class="mt-3">
            <h6 class="text-primary">可用工具 (${serverInfo.tools.length} 个)</h6>
            <div class="border rounded p-3" style="max-height: 300px; overflow-y: auto;">
    `;

    if (serverInfo.tools && serverInfo.tools.length > 0) {
        contentHtml += '<div class="d-flex flex-wrap gap-2">';

        serverInfo.tools.forEach(tool => {
            contentHtml += `
                <span class="badge bg-secondary fs-6 px-2 py-1">
                    <i class="fas fa-tool"></i> ${tool.name || window.i18n.t('tool.unknown')}
                </span>
            `;
        });

        contentHtml += '</div>';
    } else {
        contentHtml += `
            <div class="text-center text-muted py-3">
                <i class="fas fa-tools fa-2x mb-2"></i>
                <p>${window.i18n.t('test.results.no.tools')}</p>
            </div>
        `;
    }

    contentHtml += `
            </div>
        </div>
    `;

    $content.html(contentHtml);

    // 显示模态框
    const testResultModal = new bootstrap.Modal(document.getElementById('testResultModal'));
    testResultModal.show();
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

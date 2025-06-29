Ext.define("js.app.resource.protection.TDMProtectionGroupAdd", {
    /*
    TODO LIST：
        1.Multi Language
        .....
    */
    requires: [],
    baseUrl: "sysapp/tdmPgAction",
    newPgData: {},
    cmp: {
        winId: "resource_management_tdmPg_Add",
        win: null,
        outerPanel: null, // ${winId}-outerPanel

        leftOuterPanel: null, // ${winId}-leftOuterPanel
        panelStep01: null, // ${winId}-step1
        panelStep02Tree: null, // ${winId}-step2tree
        panelStep03Tree: null, // ${winId}-step3tree

        rightOuterPanel: null, // ${winId}-rightOuterPanel
        panelStep02: null, // ${winId}-step2
        panelStep03: null, // ${winId}-step3
    },
    datas: {
        neList: [],
        groupNameList: [],
    },
    // --- 紀錄當前設定進度
    progress: {
        idx: 0,
        cmpList: [],
        restart: function () {
            while(this.idx > 0){
                this.backward();
            }
        },
        forward: function () {
            this.idx++;
            switch(this.idx){
                case 1:
                    const step1Form = this.cmpList[this.idx - 1];
                    step1Form.mask();

                    if (!step1Form.isValid()) {
                        parent.warning("必要欄位未填寫。");
                        return;
                    }
                    step1Form.submit({
                        success: function (form, action) {
                            const res = action.result;
                            parent.newPgData = res.data;

                            Ext.getCmp("btn_restart_setting").enable();
                            Ext.getCmp("btn_pre_step").enable();
                        },
                        failure: function (form, action) {
                            const res = JSON.parse(action.response.responseText);
                            Ext.Msg.alert("設定失敗", res.msg);
                            step1Form.unmask();
                        },
                    });
                    break;

                case 2:
                    break;

                case 3:
                    break;                
            }
            this.updateStatus();
        },
        backward: function () {
            switch(this.idx){
                case 1:
                    parent.delStep1Data();
                    Ext.getCmp("btn_restart_setting").disable();
                    Ext.getCmp("btn_pre_step").disable();
                    break;

                case 2:
                    parent.delStep2Data();
                    break;

                case 3:
                    parent.delStep3Data();
                    break;                
            }
            this.idx--;
            this.updateStatus();
        },
        updateStatus: function () {
            // --- 處理主畫面
            for (let i = 0; i < this.cmpList.length; i++) {
                const cmp = this.cmpList[i];
                if (!cmp) continue; // 安全防呆
                console.log({i, cmp});

                if (i < this.idx) {
                    cmp.mask("Done", "icon_ok");
                } else if (i === this.idx) {                    
                    cmp.enable();
                    cmp.unmask();
                } else {
                    cmp.disable();
                }
            }
            
            // --- 處理按鈕
            if (this.done()) Ext.getCmp("btn_complete_setting").enable();
        },
        done:function(){
            return this.idx === this.cmpList.length;
        }
    },
    createWindow: function () {
        const me = this;

        const neList = Boat.Synchronize(me.baseUrl + "?method=neList").data;
        console.log({ neList });
        me.datas.neList = neList;

        const groupNameList = Boat.Synchronize(me.baseUrl + "?method=groupNameList").data;
        console.log({ data2: groupNameList });
        me.datas.groupNameList = groupNameList;

        let winId = me.cmp.winId;
        let win = desktop.getWindow(winId);
        if (!win) {
            win = Ext.create("Ext.window.Window", {
                id: winId,
                iconCls: "resmanagement_add",
                title: `${getTextByCid("Create New Protection Group")}`, // Create New Protection Group
                width: 900,
                height: 650,
                maximizable: false,
                maximized: false,
                resizable: false,
                minimizable: false,
                modal: true,
                layout: "fit", // 塞入一個 border panel
                items: [
                    {
                        id: winId + "-outerPanel",
                        xtype: "panel",
                        layout: "border", // 重點：用 border 分左右
                        border: false,
                        items: [me.genLeftOuterPanel(winId), me.genRightOuterPanel(winId)],
                    },
                ],
                bbar: [
                    {
                        xtype: "button",
                        text: getTextByCid("Close"),
                        iconCls: "button-cancel",
                        handler: function () {
                            me.closeWin();
                        },
                    },
                    {
                        id: "btn_restart_setting",
                        xtype: "button",
                        text: getTextByCid("Restart Setting"),
                        iconCls: "button-reset",
                        disabled: true,
                        handler: function () {
                            let hint = "確定放棄目前設定的資料，回到步驟一?";
                            me.confirmWin(hint, function () {
                                me.progress.restart();
                            });
                        },
                    },
                    "->",
                    {
                        id: "btn_pre_step",
                        xtype: "button",
                        text: getTextByCid("Previous Step"),
                        iconCls: "button-reset",
                        disabled: true,
                        handler: function () {
                            me.progress.backward();
                        },
                    },                    
                    {
                        id: "btn_complete_setting",
                        xtype: "button",
                        text: getTextByCid("Complete Setting"),
                        iconCls: "button-ok",
                        disabled: true,
                        handler: function () {
                            alert("Developing！");
                        },
                    },
                ],
                listeners: {
                    show: function () {
                        console.log("--- Show：TDMProtectionGroupAdd");
                    },
                    beforeclose: function (win) {
                        let hint = "尚未成功創建Protection Group，確定放棄目前設定的資料?";
                        me.confirmWin(hint, function () {
                            // 清除當前資料group資料
                            me.delStep1Data();
                            win.destroy();
                        });
                        return false;
                    },
                },
            });
        }
        me.cmp.win = win;

        me.progress.parent = me;
        me.progress.cmpList.push(Ext.getCmp(winId + "step1"));
        me.progress.cmpList.push(Ext.getCmp(winId + "step2"));
        me.progress.cmpList.push(Ext.getCmp(winId + "step3"));
        
        return win;
    },
    genLeftOuterPanel(winId) {
        const me = this;
        let leftPid = winId + "-leftOuterPanel";

        // 左側視窗由多個Panel進行切換
        const leftPanel = {
            id: leftPid,
            xtype: "panel",
            layout: "card", // *** 這種layout支援切換畫面
            region: "west",
            width: 450,
            activeItem: 0, // 預設顯示第一個item
            items: [me.genPanelStep1(winId), me.genPanelStep2Tree(winId), me.genPanelStep3Tree(winId)],
        };

        me.cmp.leftOuterPanel = leftPanel;
        return leftPanel;
    },
    genPanelStep1(winId) {
        const me = this;
        let step1Pid = winId + "-step1";
        let requiredMark = `<span style="color:red;">*</span>`;

        const step1Panel = new Ext.form.FormPanel({
            id: step1Pid,
            iconCls: "alarm-panel-setup",
            itemId: "left_default_panel",
            title: "Step 1：Basic Settings",
            defaults: {
                anchor: "0",
                style: "margin:10px 20px 0 10px;",
            },
            url: me.baseUrl + "?method=addPg", // TODO:: 完成創建group的API
            items: [
                {
                    xtype: "combo",
                    name: "equipCode",
                    fieldLabel: "NE Label" + requiredMark,
                    labelWidth: 150,
                    allowBlank: false,
                    store: Ext.create("Ext.data.Store", {
                        fields: ["neLabel", "equipCode"],
                        data: me.datas.neList,
                    }),
                    value: null,
                    queryMode: "local",
                    displayField: "neLabel",
                    valueField: "equipCode",
                    listeners: {
                        change: function (field, newValue, oldValue, eOpts) {
                            // --- 更新OK鈕的狀態
                            me.checkStep1CanOK();
                        },
                    },
                },
                {
                    xtype: "textfield",
                    name: "groupName",
                    fieldLabel: "Group Name" + requiredMark,
                    labelWidth: 150,
                    allowBlank: false,
                    validator: function (input) {
                        if (me.datas.groupNameList.includes(input)) {
                            return "Group Name already exists, please input another one.";
                        }
                        return true;
                    },
                    listeners: {
                        change: function (field, newValue, oldValue, eOpts) {
                            // --- 更新OK鈕的狀態
                            me.checkStep1CanOK();
                        },
                    },
                },
                {
                    xtype: "combo",
                    name: "protection",
                    fieldLabel: "Protection" + requiredMark,
                    labelWidth: 150,
                    allowBlank: false,
                    store: Ext.create("Ext.data.Store", {
                        fields: ["value", "name"],
                        data: [
                            {
                                name: "Card 1:1",
                                value: "card11",
                            },
                            {
                                name: "Card 1:N",
                                value: "card1n",
                            },
                            {
                                name: "MSP 1+1",
                                value: "msp11",
                            },
                            {
                                name: "SNCP_UPSR",
                                value: "sncp_upsr",
                            },
                        ],
                    }),
                    value: null,
                    queryMode: "local",
                    displayField: "name",
                    valueField: "value",
                    listeners: {
                        change: function (field, newValue, oldValue, eOpts) {
                            // --- 更新OK鈕的狀態
                            me.checkStep1CanOK();
                        },
                    },
                },
                {
                    xtype: "combo",
                    name: "reversionMode",
                    fieldLabel: "Revertive Mode" + requiredMark,
                    allowBlank: false,
                    store: Ext.create("Ext.data.Store", {
                        fields: ["value", "name"],
                        data: [
                            {
                                name: "Revertive",
                                value: "revertive",
                            },
                            {
                                name: "Non Revertive",
                                value: "non_evertive",
                            },
                        ],
                    }),
                    labelWidth: 150,
                    value: null,
                    queryMode: "local",
                    displayField: "name",
                    valueField: "value",
                    listeners: {
                        change: function (field, newValue, oldValue, eOpts) {
                            // --- 更新OK鈕的狀態
                            me.checkStep1CanOK();
                        },
                    },
                },
                {
                    xtype: "textfield",
                    name: "remark",
                    fieldLabel: "Remark",
                    labelWidth: 150,
                },
            ],
            bbar: [
                "->",
                {
                    id: "btn_step1_reset",
                    xtype: "button",
                    text: getTextByCid("Reset"),
                    iconCls: "button-reset",
                    handler: function () {
                        const form = Ext.getCmp(winId + "-step1");
                        form.reset();
                    },
                },
                {
                    id: "btn_step1_ok",
                    xtype: "button",
                    text: getTextByCid("OK"),
                    iconCls: "button-ok",
                    disabled: true,
                    handler: function () {
                        me.progress.forward();
                    },
                },
            ],
        });

        me.cmp.panelStep01 = step1Panel;
        return step1Panel;
    },
    genPanelStep2Tree(winId) {
        const me = this;
        let treePid = winId + "-step2tree";

        const treeTestData = [
            {
                expanded: true,
                visible: true,
                children: [
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000083203",
                        checked: false,
                        disabled: false,
                        text: "G7800_101",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000082250",
                        checked: false,
                        disabled: false,
                        text: "G7800_100",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000068946",
                        checked: false,
                        disabled: false,
                        text: "G7800_102",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                ],
                keyValue: "G7800A_1",
                checked: false,
                disabled: false,
                text: "G7800A_1",
                iconCls: "device-poller-icon",
                leaf: false,
            },
            {
                expanded: true,
                visible: true,
                children: [
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000061543",
                        checked: false,
                        disabled: false,
                        text: "AM3440_107",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                ],
                keyValue: "AM3440A_1",
                checked: false,
                disabled: false,
                text: "AM3440A_1",
                iconCls: "device-poller-icon",
                leaf: false,
            },
        ];
        const treeStore = new Ext.data.TreeStore({
            root: {
                expanded: true,
                children: treeTestData,
            },
            events: {},
        });
        const treePanel = new Ext.tree.Panel({
            id: treePid,
            itemId: "left_step02_panel",
            title: "Setting Primary Object",
            iconCls: "button-setting",

            width: 450,
            height: 550,
            layout: "fit",
            autoScroll: true,
            rootVisible: true,
            split: true,
            store: treeStore,
            bbar: [
                "->",
                {
                    xtype: "button",
                    text: getTextByCid("Cancel"),
                    iconCls: "button-cancel",
                    handler: function () {
                        // --- 切回step1面板
                        Ext.getCmp(winId + "-leftOuterPanel")
                            .getLayout()
                            .setActiveItem("left_default_panel");

                        // --- 解鎖右側面板
                        Ext.getCmp(winId + "-rightOuterPanel").enable();
                    },
                },
                {
                    id: "btn_step2_add_ok",
                    xtype: "button",
                    text: getTextByCid("OK"),
                    iconCls: "button-ok",
                    disabled: true,
                    handler: function () {
                        alert("Developing！");
                    },
                },
            ],
        });
        me.cmp.panelStep02Tree = treePanel;
        return treePanel;
    },
    genPanelStep3Tree(winId) {
        const me = this;
        let treePid = winId + "-step3tree";

        const treeTestData = [
            {
                expanded: true,
                visible: true,
                children: [
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000053564",
                        checked: false,
                        disabled: false,
                        text: "O94PTN_100",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000052424",
                        checked: false,
                        disabled: false,
                        text: "O94PTN_104",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                ],
                keyValue: "O94PTN_1",
                checked: false,
                disabled: false,
                text: "O94PTN_1",
                iconCls: "device-poller-icon",
                leaf: false,
            },
            {
                expanded: true,
                visible: true,
                children: [
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000050123",
                        checked: false,
                        disabled: false,
                        text: "O95PTN_101",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000088390",
                        checked: false,
                        disabled: false,
                        text: "O95PTN_103",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000057418",
                        checked: false,
                        disabled: false,
                        text: "O95PTN_100",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                ],
                keyValue: "O95PTN_1",
                checked: false,
                disabled: false,
                text: "O95PTN_1",
                iconCls: "device-poller-icon",
                leaf: false,
            },
            {
                expanded: true,
                visible: true,
                children: [
                    {
                        expanded: false,
                        visible: true,
                        keyValue: "10000000000000088361",
                        checked: false,
                        disabled: false,
                        text: "server_161",
                        iconCls: "equipment-NE-panel",
                        leaf: true,
                    },
                ],
                keyValue: "GenericNE_1",
                checked: false,
                disabled: false,
                text: "GenericNE_1",
                iconCls: "device-poller-icon",
                leaf: false,
            },
        ];
        const treeStore = new Ext.data.TreeStore({
            root: {
                expanded: true,
                children: treeTestData,
            },
            events: {},
        });
        const treePanel = new Ext.tree.Panel({
            id: treePid,
            itemId: "left_step03_panel",
            title: "Setting Secondary Object",
            iconCls: "button-setting",

            width: 450,
            height: 550,
            layout: "fit",
            autoScroll: true,
            rootVisible: true,
            split: true,
            store: treeStore,
            bbar: [
                "->",
                {
                    xtype: "button",
                    text: getTextByCid("Cancel"),
                    iconCls: "button-cancel",
                    handler: function () {
                        // --- 切回step1面板
                        Ext.getCmp(winId + "-leftOuterPanel")
                            .getLayout()
                            .setActiveItem("left_default_panel");

                        // --- 解鎖右側面板
                        Ext.getCmp(winId + "-rightOuterPanel").enable();
                    },
                },
                {
                    id: "btn_step3_add_ok",
                    xtype: "button",
                    text: getTextByCid("OK"),
                    iconCls: "button-ok",
                    disabled: true,
                    handler: function () {
                        alert("Developing！");
                    },
                },
            ],
        });
        me.cmp.panelStep03Tree = treePanel;
        return treePanel;
    },
    genRightOuterPanel(winId) {
        const me = this;
        let rightPid = winId + "-rightOuterPanel";
        const rightOuterPanel = {
            id: rightPid,
            xtype: "panel",
            region: "center",
            title: "Realtion Setting",
            header: false,
            layout: {
                type: "vbox",
                align: "stretch", // 滿版寬度
            },
            items: [me.genPanelStep2(winId), me.genPanelStep3(winId)],
        };
        me.cmp.rightOuterPanel = rightOuterPanel;
        return rightOuterPanel;
    },
    // --- Step 2：Primary Object
    genPanelStep2(winId) {
        const me = this;
        let step2Pid = winId + "-step2";
        const step2Panel = {
            id: step2Pid,
            title: "Step 2：Primary Object",
            iconCls: "icon_pg_relation_setting",
            region: "north",
            height: 295,
            xtype: "panel",
            layout: "fit",
            disabled: true,
            bbar: [
                // "->",
                {
                    id: "btn_step2_add",
                    xtype: "button",
                    text: getTextByCid("Add"),
                    iconCls: "button-add",
                    handler: function () {
                        // --- 顯示左側資源樹
                        Ext.getCmp(winId + "-leftOuterPanel")
                            .getLayout()
                            .setActiveItem("left_step02_panel");

                        // --- 鎖住右側面板
                        Ext.getCmp(winId + "-rightOuterPanel").disable();
                    },
                },
                {
                    id: "btn_step2_remove",
                    xtype: "button",
                    text: getTextByCid("Remove"),
                    iconCls: "button-del",
                    disabled: true,
                    handler: function () {},
                },
                "->",
                {
                    id: "btn_step2_ok",
                    xtype: "button",
                    text: getTextByCid("OK"),
                    iconCls: "button-ok",
                    disabled: true,
                    handler: function () {
                        me.progress.forward();
                    },
                },
            ],
        };

        me.cmp.panelStep02 = step2Panel;
        return step2Panel;
    },
    // --- Step 3：Secondary Object
    genPanelStep3(winId) {
        const me = this;
        let step3Pid = winId + "-step3";
        const step3Panel = {
            id: step3Pid,
            title: "Step 3：Secondary Object",
            iconCls: "icon_pg_relation_setting",
            region: "center",
            height: 290,
            xtype: "panel",
            layout: "fit",
            disabled: true,
            bbar: [
                // "->",
                {
                    id: "btn_step3_add",
                    xtype: "button",
                    text: getTextByCid("Add"),
                    iconCls: "button-add",
                    handler: function () {
                        // --- 顯示左側資源樹
                        Ext.getCmp(winId + "-leftOuterPanel")
                            .getLayout()
                            .setActiveItem("left_step03_panel");

                        // --- 鎖住右側面板
                        Ext.getCmp(winId + "-rightOuterPanel").disable();
                    },
                },
                {
                    id: "btn_step3_remove",
                    xtype: "button",
                    text: getTextByCid("Remove"),
                    iconCls: "button-del",
                    disabled: true,
                    handler: function () {},
                },
                "->",
                {
                    id: "btn_step3_ok",
                    xtype: "button",
                    text: getTextByCid("OK"),
                    iconCls: "button-ok",
                    disabled: true,
                    handler: function () {
                        me.progress.forward();
                    },
                },
            ],
        };

        me.cmp.panelStep03 = step3Panel;
        return step3Panel;
    },
    delStep1Data() {
        const me = this;

        // --- 清空本地資料
        me.newPgData = {};

        // --- 送出刪除資料的API
        Ext.Ajax.request({
            url: me.baseUrl + "?method=delPg", // 你的 API 路徑
            method: "POST",
            params: {
                groupCode: me.newPgData.groupCode,
            },
            success: function (response) {
                const result = Ext.decode(response.responseText);
                console.log({ response, result });
            },
            failure: function (response) {
                console.log({ response });
                Ext.Msg.alert("刪除失敗", response.msg);
            },
        });
    },
    delStep2Data() {
        const me = this;
        // TODO:: 刪除畫面資料
    },
    delStep3Data() {
        const me = this;
        // TODO:: 刪除畫面資料
    },
    checkStep1CanOK() {
        const me = this;

        const form = Ext.getCmp(me.cmp.winId + "-step1");
        const btnOk = Ext.getCmp("btn_step1_ok");

        if (form.isValid()) {
            btnOk.enable();
        } else {
            btnOk.disable();
        }
    },
    closeWin() {
        const me = this;
        me.cmp.win.close();
    },
    confirmWin(hint, yCallback, nCallback) {
        const me = this;
        Ext.MessageBox.setAlwaysOnTop(true);
        Ext.MessageBox.confirm(
            getTextByCid("130056000036"), // 提示
            hint,
            function (btn) {
                console.log(btn);
                if (btn == "yes") yCallback();
                if (btn == "no" && nCallback) nCallback();
            },
            me
        );
    },
});

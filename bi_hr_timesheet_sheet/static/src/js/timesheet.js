///** @odoo-module **/
////import { core } from "@web/core";
////import { registry } from "@web/core/registry";
////var data = require('web.data');
//var form_common = require('web.form_common');
////var formats = require('web.formats');
////var Model = require('web.DataModel');
////var time = require('web.time');
////var utils = require('web.utils');
////
////var QWeb = core.qweb;
//import { _t } from "@web/core/l10n/translation";
//
//console.log("jkhkjhkd")
//
//var WeeklyTimesheet = form_common.FormWidget.extend(form_common.ReinitializeWidgetMixin, {
//    events: {
//        "click .oe_timesheet_weekly_account a": "go_to",
//    },
//    ignore_fields: function() {
//        return ['line_id'];
//    },
//    init: function() {
//        this._super.apply(this, arguments);
//        this.set({
//            sheets: [],
//            date_from: false,
//            date_to: false,
//        });
//        this.field_manager.on("field_changed:timesheet_ids", this, this.query_sheets);
//        this.field_manager.on("field_changed:date_from", this, function() {
//            this.set({"date_from": time.str_to_date(this.field_manager.get_field_value("date_from"))});
//        });
//        this.field_manager.on("field_changed:date_to", this, function() {
//            this.set({"date_to": time.str_to_date(this.field_manager.get_field_value("date_to"))});
//        });
//        this.field_manager.on("field_changed:user_id", this, function() {
//            this.set({"user_id": this.field_manager.get_field_value("user_id")});
//        });
//        this.on("change:sheets", this, this.update_sheets);
//        this.res_o2m_drop = new utils.DropMisordered();
//        this.render_drop = new utils.DropMisordered();
//        this.description_line = _t("/");
//    },
//
//});
////
////core.form_custom_registry.add('weekly_timesheet', WeeklyTimesheet);
////
////});

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProformaInvoice(models.Model):
    _name = "proforma.invoice"
    _description = "Proforma Invoice"
    _order = "date_invoice desc"

    name = fields.Char(string="Proforma Invoice Number", copy=False, readonly=True, index=True, default=lambda self: 'New')
    partner_id = fields.Many2one("res.partner", string="Customer", required=True)
    date_invoice = fields.Date(string="Invoice Date", default=fields.Date.context_today)
    validity_date = fields.Date(string="Validity Date")
    invoice_line_ids = fields.One2many("proforma.invoice.line", "invoice_id", string="Invoice Lines")
    amount_total = fields.Monetary(string="Total Amount", compute="_compute_total", store=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled")
    ], string="Status", default="draft", required=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, string="Currency")
    notes = fields.Text(string="Additional Notes")
    payment_certificate_no = fields.Char(
        string='Payment Certificate No',
    )
    job_order_id = fields.Many2one('job.order', string="Job Order")

    @api.depends("invoice_line_ids.subtotal")
    def _compute_total(self):
        for record in self:
            record.amount_total = sum(line.subtotal for line in record.invoice_line_ids)

    @api.model
    def create(self, vals):
        """Generate a unique sequence number for Proforma Invoice."""
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("proforma.invoice") or "New"
        return super(ProformaInvoice, self).create(vals)


    def action_confirm(self):
        if not self.payment_certificate_no:
            raise ValidationError(_("Please add the Payment Certificate No"))

        confirm_state = self.write({'state': 'confirmed'})

        return {
            "name": "Work order",
            "type": "ir.actions.act_window",
            "res_model": "job.order",
            "view_mode": "form",
            "res_id": self.job_order_id.id,
            "target": "current",
        }

    def action_sent(self):
        sent_state = self.write({'state': 'sent'})
        return sent_state

    def action_draft(self):
        draft_state = self.write({'state': 'draft'})
        return draft_state

    def action_Cancel(self):
        cancel_state = self.write({'state': 'cancelled'})
        return cancel_state


class ProformaInvoiceLine(models.Model):
    _name = "proforma.invoice.line"
    _description = "Proforma Invoice Line"

    invoice_id = fields.Many2one("proforma.invoice", string="Proforma Invoice", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product/Service", required=True)
    quantity = fields.Float(string="Quantity", default=1.0)
    price_unit = fields.Float(string="Unit Price", required=True)
    subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal", store=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", string="Currency", readonly=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

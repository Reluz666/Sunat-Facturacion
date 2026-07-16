"""
Generador de XML UBL 2.1 para comprobantes electrónicos SUNAT.

Genera XML con estructura UBL 2.1 que incluye:
  - Namespaces estándar UBL (cbc, cac, ext, ds)
  - Firma digital mock (hash SHA-256)
  - AccountingSupplierParty (datos empresa)
  - AccountingCustomerParty (datos cliente)
  - TaxTotal con IGV (código 1000)
  - LegalMonetaryTotal con desglose
  - InvoiceLine[] con detalle por línea

La firma digital es un mock (hash SHA-256 del contenido XML).
En producción se reemplazaría con una firma real usando certificado digital.
"""
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from lxml import etree
from decouple import config
from apps.comprobantes.signer import SunatSigner

logger = logging.getLogger(__name__)


# ── Namespaces UBL 2.1 ──────────────────────────────────────────────
NSMAP = {
    None: 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
}

SAC = 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'

CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
DS  = 'http://www.w3.org/2000/09/xmldsig#'

# Mapeo de tipos de comprobante a códigos SUNAT
TIPO_DOCUMENTO_SUNAT = {
    'FACTURA': '01',
    'BOLETA': '03',
    'NOTA_CREDITO': '07',
}

TIPO_DOCUMENTO_IDENTIDAD = {
    'DNI': '1',
    'CE': '4',
    'RUC': '6',
    'PASAPORTE': '7',
}


def _cbc(parent, tag, text, **attribs):
    """Helper: crea un subelemento cbc:Tag con texto y atributos."""
    elem = etree.SubElement(parent, f'{{{CBC}}}{tag}')
    elem.text = str(text)
    for k, v in attribs.items():
        elem.set(k, str(v))
    return elem


def _cac(parent, tag):
    """Helper: crea un subelemento cac:Tag."""
    return etree.SubElement(parent, f'{{{CAC}}}{tag}')


def generar_xml_comprobante(comprobante):
    """
    Genera un XML UBL 2.1 para el comprobante electrónico.

    Args:
        comprobante: instancia de Comprobante con detalles cargados.

    Returns:
        tuple (xml_string, hash_cpe)
          - xml_string: XML como string UTF-8.
          - hash_cpe: SHA-256 del contenido XML (firma mock).

    Estructura XML generada:
        <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
          <UBLExtensions>
            <UBLExtension>
              <ExtensionContent>
                <Signature> ... (firma mock) </Signature>
              </ExtensionContent>
            </UBLExtension>
          </UBLExtensions>
          <UBLVersionID>2.1</UBLVersionID>
          <CustomizationID>2.0</CustomizationID>
          <ID>F001-00001</ID>
          <IssueDate>2026-05-13</IssueDate>
          <InvoiceTypeCode>01</InvoiceTypeCode>
          <DocumentCurrencyCode>PEN</DocumentCurrencyCode>
          <AccountingSupplierParty> ... </AccountingSupplierParty>
          <AccountingCustomerParty> ... </AccountingCustomerParty>
          <TaxTotal> ... </TaxTotal>
          <LegalMonetaryTotal> ... </LegalMonetaryTotal>
          <InvoiceLine> ... </InvoiceLine>
        </Invoice>
    """
    # Cargar relaciones necesarias
    detalles = comprobante.detalles
    empresa = comprobante.empresa
    cliente = comprobante.cliente

    tipo_codigo = TIPO_DOCUMENTO_SUNAT.get(comprobante.tipo, '01')
    is_credit_note = (comprobante.tipo == 'NOTA_CREDITO')

    # ═══ Raíz del documento con Namespace explícito ═══════════════
    root_ns = 'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2' if is_credit_note else NSMAP[None]
    root_tag = 'CreditNote' if is_credit_note else 'Invoice'
    
    nsmap = NSMAP.copy()
    nsmap[None] = root_ns

    invoice = etree.Element(f'{{{root_ns}}}{root_tag}', nsmap=nsmap)

    # ── UBLExtensions ─────────────────────────────────────────────
    extensions = etree.SubElement(invoice, f'{{{EXT}}}UBLExtensions')
    
    # Extension 1: Para la firma digital (se llenará en SunatSigner.sign_xml())
    extension = etree.SubElement(extensions, f'{{{EXT}}}UBLExtension')
    ext_content = etree.SubElement(extension, f'{{{EXT}}}ExtensionContent')

    # Extension 2: AdditionalInformation requerido por SUNAT
    ext_add = etree.SubElement(extensions, f'{{{EXT}}}UBLExtension')
    ext_add_content = etree.SubElement(ext_add, f'{{{EXT}}}ExtensionContent')
    sac_additional = etree.SubElement(ext_add_content, f'{{{SAC}}}AdditionalInformation')
    sac_monetary = etree.SubElement(sac_additional, f'{{{SAC}}}AdditionalMonetaryTotal')
    _cbc(sac_monetary, 'ID', '1001')
    _cbc(sac_monetary, 'PayableAmount', f'{comprobante.subtotal:.2f}', currencyID='PEN')

    # ── Metadatos del comprobante (UBL 2.0) ───────────────────────
    _cbc(invoice, 'UBLVersionID', '2.0')
    _cbc(invoice, 'CustomizationID', '1.0' if is_credit_note else '1.1')
    
    if not is_credit_note:
        _cbc(invoice, 'ProfileID', '0101', 
             schemeName="SUNAT:Identificador de Tipo de Operación", 
             schemeAgencyName="PE:SUNAT", 
             schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo17")

    _cbc(invoice, 'ID', comprobante.serie_numero)
    _cbc(invoice, 'IssueDate', comprobante.fecha_emision.strftime('%Y-%m-%d'))
    
    if not is_credit_note:
        _cbc(invoice, 'InvoiceTypeCode', tipo_codigo, 
             listAgencyName="PE:SUNAT", 
             listURI="urn:pe:sunat:catalog:01",
             listName="Tipo de Documento",
             listID="0101")
             
    _cbc(invoice, 'DocumentCurrencyCode', 'PEN', 
         listID="ISO 4217 Alpha",
         listName="Currency",
         listAgencyName="United Nations Economic Commission for Europe")
    
    _cbc(invoice, 'LineCountNumeric', str(len(detalles)))

    if is_credit_note:
        # Recuperar la nota de crédito de forma segura, incluso si la caché del objeto no la tiene
        from apps.comprobantes.models import NotaCredito
        try:
            nota_info = NotaCredito.objects.get(comprobante_nota_id=comprobante.id)
            # DiscrepancyResponse
            discrepancy = _cac(invoice, 'DiscrepancyResponse')
            _cbc(discrepancy, 'ReferenceID', nota_info.comprobante_referencia.serie_numero)
            _cbc(discrepancy, 'ResponseCode', nota_info.tipo_nota)
            _cbc(discrepancy, 'Description', nota_info.motivo.strip() if nota_info.motivo and nota_info.motivo.strip() else 'Nota de Crédito')
            
            # BillingReference
            billing_ref = _cac(invoice, 'BillingReference')
            inv_doc_ref = _cac(billing_ref, 'InvoiceDocumentReference')
            _cbc(inv_doc_ref, 'ID', nota_info.comprobante_referencia.serie_numero)
            _cbc(inv_doc_ref, 'DocumentTypeCode', TIPO_DOCUMENTO_SUNAT.get(nota_info.comprobante_referencia.tipo, '01'))
        except NotaCredito.DoesNotExist:
            pass

    # ── Firma referencia ──────────────────────────────────────────
    signature_ref = _cac(invoice, 'Signature')
    _cbc(signature_ref, 'ID', 'SignatureSUNAT')
    sig_party = _cac(signature_ref, 'SignatoryParty')
    sig_party_ident = _cac(sig_party, 'PartyIdentification')
    _cbc(sig_party_ident, 'ID', empresa.ruc)

    # ═══ AccountingSupplierParty (formato UBL 2.0) ═════════════════
    supplier = _cac(invoice, 'AccountingSupplierParty')
    _cbc(supplier, 'CustomerAssignedAccountID', empresa.ruc)
    _cbc(supplier, 'AdditionalAccountID', '6')
    
    supplier_party = _cac(supplier, 'Party')
    supplier_name = _cac(supplier_party, 'PartyName')
    _cbc(supplier_name, 'Name', empresa.razon_social)
    supplier_legal = _cac(supplier_party, 'PartyLegalEntity')
    _cbc(supplier_legal, 'RegistrationName', empresa.razon_social)

    # ═══ AccountingCustomerParty (formato UBL 2.0) ═════════════════
    customer = _cac(invoice, 'AccountingCustomerParty')
    tipo_doc_code = TIPO_DOCUMENTO_IDENTIDAD.get(cliente.tipo_doc, '0')
    _cbc(customer, 'CustomerAssignedAccountID', cliente.num_doc)
    _cbc(customer, 'AdditionalAccountID', tipo_doc_code)
    
    customer_party = _cac(customer, 'Party')
    customer_legal = _cac(customer_party, 'PartyLegalEntity')
    _cbc(customer_legal, 'RegistrationName', cliente.razon_social)

    # ═══ TaxTotal (IGV global) ════════════════════════════════════
    tax_total = _cac(invoice, 'TaxTotal')
    _cbc(tax_total, 'TaxAmount', f'{comprobante.igv:.2f}', currencyID='PEN')

    tax_subtotal = _cac(tax_total, 'TaxSubtotal')
    _cbc(tax_subtotal, 'TaxableAmount', f'{comprobante.subtotal:.2f}', currencyID='PEN')
    _cbc(tax_subtotal, 'TaxAmount', f'{comprobante.igv:.2f}', currencyID='PEN')

    tax_category = _cac(tax_subtotal, 'TaxCategory')
    _cbc(tax_category, 'ID', 'S', schemeID='UN/ECE 5305', schemeName='Tax Category Identifier', schemeAgencyName='United Nations Economic Commission for Europe')
    
    tax_scheme = _cac(tax_category, 'TaxScheme')
    _cbc(tax_scheme, 'ID', '1000', schemeID='UN/ECE 5153', schemeAgencyID='6')
    _cbc(tax_scheme, 'Name', 'IGV')
    _cbc(tax_scheme, 'TaxTypeCode', 'VAT')

    # ── Total Inafecto (si aplica) ────────────────────────────────
    if comprobante.total_inafecto > 0:
        tax_total_inaf = _cac(invoice, 'TaxTotal')
        _cbc(tax_total_inaf, 'TaxAmount', '0.00', currencyID='PEN')

        tax_subtotal_inaf = _cac(tax_total_inaf, 'TaxSubtotal')
        _cbc(tax_subtotal_inaf, 'TaxableAmount', f'{comprobante.total_inafecto:.2f}', currencyID='PEN')
        _cbc(tax_subtotal_inaf, 'TaxAmount', '0.00', currencyID='PEN')

        tax_cat_inaf = _cac(tax_subtotal_inaf, 'TaxCategory')
        _cbc(tax_cat_inaf, 'ID', 'E', schemeID='UN/ECE 5305', schemeName='Tax Category Identifier', schemeAgencyName='United Nations Economic Commission for Europe')
        
        tax_scheme_inaf = _cac(tax_cat_inaf, 'TaxScheme')
        _cbc(tax_scheme_inaf, 'ID', '9998', schemeID='UN/ECE 5153', schemeAgencyID='6')
        _cbc(tax_scheme_inaf, 'Name', 'INA')
        _cbc(tax_scheme_inaf, 'TaxTypeCode', 'FRE')

    # ═══ LegalMonetaryTotal ═══════════════════════════════════════
    monetary = _cac(invoice, 'LegalMonetaryTotal')
    _cbc(monetary, 'LineExtensionAmount', f'{comprobante.subtotal:.2f}', currencyID='PEN')
    _cbc(monetary, 'TaxInclusiveAmount', f'{comprobante.total:.2f}', currencyID='PEN')
    _cbc(monetary, 'PayableAmount', f'{comprobante.total:.2f}', currencyID='PEN')

    # ═══ InvoiceLine / CreditNoteLine (detalle por línea) ══════════════════════════
    line_tag = 'CreditNoteLine' if is_credit_note else 'InvoiceLine'
    qty_tag = 'CreditedQuantity' if is_credit_note else 'InvoicedQuantity'
    
    for idx, detalle in enumerate(detalles, 1):
        line = _cac(invoice, line_tag)
        _cbc(line, 'ID', str(idx))
        _cbc(line, qty_tag, f'{detalle.cantidad:.2f}',
             unitCode=detalle.producto.unidad_medida)
        _cbc(line, 'LineExtensionAmount', f'{detalle.subtotal:.2f}', currencyID='PEN')

        # PricingReference
        pricing = _cac(line, 'PricingReference')
        alt_price = _cac(pricing, 'AlternativeConditionPrice')
        
        # El precio debe incluir el IGV para este tag
        precio_con_igv = detalle.precio_unitario * (Decimal('1.18') if detalle.producto.afecto_igv else Decimal('1.00'))
        _cbc(alt_price, 'PriceAmount', f'{precio_con_igv:.2f}', currencyID='PEN')
        _cbc(alt_price, 'PriceTypeCode', '01', 
             listName='SUNAT:Indicador de Tipo de Precio', 
             listAgencyName='PE:SUNAT', 
             listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16')

        # AllowanceCharge — Descuento por línea (DEBE ir antes de TaxTotal según UBL 2.1)
        if detalle.descuento > 0:
            allowance = _cac(line, 'AllowanceCharge')
            _cbc(allowance, 'ChargeIndicator', 'false')
            _cbc(allowance, 'AllowanceChargeReasonCode', '00')
            _cbc(allowance, 'MultiplierFactorNumeric', f'{detalle.descuento / 100:.4f}')
            base_amount = detalle.cantidad * detalle.precio_unitario
            desc_monto = base_amount * (detalle.descuento / 100)
            _cbc(allowance, 'Amount', f'{desc_monto:.2f}', currencyID='PEN')
            _cbc(allowance, 'BaseAmount', f'{base_amount:.2f}', currencyID='PEN')

        # TaxTotal por línea
        line_tax = _cac(line, 'TaxTotal')
        _cbc(line_tax, 'TaxAmount', f'{detalle.igv_linea:.2f}', currencyID='PEN')

        line_tax_sub = _cac(line_tax, 'TaxSubtotal')
        _cbc(line_tax_sub, 'TaxableAmount', f'{detalle.subtotal:.2f}', currencyID='PEN')
        _cbc(line_tax_sub, 'TaxAmount', f'{detalle.igv_linea:.2f}', currencyID='PEN')

        line_tax_cat = _cac(line_tax_sub, 'TaxCategory')
        _cbc(line_tax_cat, 'ID', 'S' if detalle.producto.afecto_igv else 'E', 
             schemeID='UN/ECE 5305', schemeName='Tax Category Identifier', schemeAgencyName='United Nations Economic Commission for Europe')
        _cbc(line_tax_cat, 'Percent', '18.00' if detalle.producto.afecto_igv else '0.00')

        # Determinar tipo de afectación
        if detalle.producto.afecto_igv:
            _cbc(line_tax_cat, 'TaxExemptionReasonCode', '10', 
                 listAgencyName='PE:SUNAT', listName='SUNAT:Codigo de Tipo de Afectación del IGV', listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07')
        else:
            _cbc(line_tax_cat, 'TaxExemptionReasonCode', '30', 
                 listAgencyName='PE:SUNAT', listName='SUNAT:Codigo de Tipo de Afectación del IGV', listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07')

        line_tax_scheme = _cac(line_tax_cat, 'TaxScheme')
        _cbc(line_tax_scheme, 'ID', '1000' if detalle.producto.afecto_igv else '9998', schemeID='UN/ECE 5153', schemeAgencyID='6')
        _cbc(line_tax_scheme, 'Name', 'IGV' if detalle.producto.afecto_igv else 'INA')
        _cbc(line_tax_scheme, 'TaxTypeCode', 'VAT' if detalle.producto.afecto_igv else 'FRE')

        # Item
        item = _cac(line, 'Item')
        _cbc(item, 'Description', detalle.producto.descripcion)

        sellers_ident = _cac(item, 'SellersItemIdentification')
        _cbc(sellers_ident, 'ID', detalle.producto.codigo)

        # Price
        price = _cac(line, 'Price')
        _cbc(price, 'PriceAmount', f'{detalle.precio_unitario:.2f}', currencyID='PEN')

    # ═══ Serializar XML sin espacios en blanco adicionales ════════
    xml_bytes = etree.tostring(invoice, pretty_print=False, xml_declaration=False, encoding='UTF-8')
    xml_string = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_bytes.decode('utf-8')

    # ═══ Firma digital REAL ═══════════════════════════════════════
    if config('SUNAT_BETA_MODE', default=True, cast=bool):
        try:
            signer = SunatSigner(
                pfx_path=config('SUNAT_CERT_PATH'),
                pfx_password=config('SUNAT_CERT_PASSWORD')
            )
            xml_string_firmado = signer.sign_xml(xml_string)
            hash_cpe = signer.get_hash(xml_string_firmado)
            return xml_string_firmado, hash_cpe
        except Exception as e:
            # Si falla la firma real en desarrollo, al menos devolvemos el mock 
            # pero notificamos en log.
            logger.error("Error en firma real: %s. Usando firma mock.", e)
    
    # ═══ Firma digital mock (fallback) ════════════════════════════
    hash_cpe = hashlib.sha256(xml_bytes).hexdigest()
    # Si llegamos aquí es porque la firma real falló, el XML ya no tiene el nodo Signature
    return xml_string, hash_cpe

import { useState, useRef, useEffect, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Box, Typography, TextField, IconButton, Paper, Chip, Button,
  Avatar, Tooltip, LinearProgress, Snackbar, Alert,
} from '@mui/material'
import {
  Send, Add, AutoAwesome, Save, Build, Download,
  Person, FolderOpen, CloudDone, CloudOff, RateReview,
} from '@mui/icons-material'
import { saveBOM, setCurrentBOM, setActiveBOMForRFQ } from '../store/slices/bomSlice'
import { chatApi, bomApi } from '../services/api'

const PHASE_NAMES = [
  '', // 0-indexed, phase 1 = index 1
  'Scope & Constraints',
  'Seller Inventory',
  'Compute Sizing',
  'Storage Sizing',
  'Network Sizing',
  'Power & Physical',
  'Build BOM',
  'Approvals',
  'Validate',
  'Procurement',
]

// Phase-specific quick-reply suggestions
const PHASE_CHIPS = [
  [],
  ['SD-WAN for 30 sites', 'Data Center for Panasonic', 'Cybersecurity for Idemia'],
  ['5 sites, 200 users per site', '10 branch offices'],
  ['Dual-socket server 256GB RAM', 'VM-based compute cluster'],
  ['100TB primary storage', 'NVMe SSD for latency-sensitive'],
  ['10Gbps WAN uplink', '1Gbps LAN switching'],
  ['5kW per rack', 'Diesel generator backup'],
  ['Finalise BOM now', 'Add Cisco SmartNet from CDW'],
  ['Save BOM', 'Send to RFQ Builder'],
  ['Validate BOM', 'Export as Excel'],
  ['Export as Excel', 'Send to RFQ'],
]

const TEMPLATES = {
  'Data Center / COLO': [
    { desc:'Full Rack 42U Colocation Space',    cat:'Hosting',           unit:'/rack/mo', price:2800,  vendor:'Equinix'     },
    { desc:'Power Feed 20A 208V Dual Circuit',  cat:'Hosting',           unit:'/rack/mo', price:480,   vendor:'Equinix'     },
    { desc:'Cross-Connect 10GbE Single-Mode',   cat:'Network & Telecom', unit:'/port/mo', price:325,   vendor:'Equinix'     },
    { desc:'MPLS Circuit 1Gbps Primary',        cat:'Network & Telecom', unit:'/ckt/mo',  price:4200,  vendor:'NTT Data'    },
    { desc:'MPLS Circuit 500Mbps Backup',       cat:'Network & Telecom', unit:'/ckt/mo',  price:2800,  vendor:'NTT Data'    },
    { desc:'DDoS Mitigation Service',           cat:'Cybersecurity',     unit:'/mo',      price:1800,  vendor:'NTT Data'    },
    { desc:'Security Operations Center 24x7',   cat:'Cybersecurity',     unit:'/mo',      price:5500,  vendor:'NTT Data'    },
    { desc:'Backup Storage 100TB',              cat:'Hosting',           unit:'/mo',      price:2100,  vendor:'NTT DOCOMO'  },
    { desc:'Disaster Recovery Orchestration',   cat:'Hosting',           unit:'/mo',      price:3200,  vendor:'NTT Data'    },
    { desc:'Remote Hands Support 8hrs/month',   cat:'Service Management',unit:'/mo',      price:640,   vendor:'Equinix'     },
  ],
  'SD-WAN': [
    { desc:'SD-WAN Edge Appliance Cisco Viptela',  cat:'Network & Telecom', unit:'/device',  price:4800,  vendor:'CDW'      },
    { desc:'SD-WAN Orchestration Platform annual', cat:'Network & Telecom', unit:'/year',    price:14500, vendor:'Cisco'    },
    { desc:'Broadband Primary Circuit 300Mbps',    cat:'Network & Telecom', unit:'/site/mo', price:420,   vendor:'NTT Data' },
    { desc:'LTE Backup Circuit',                   cat:'Network & Telecom', unit:'/site/mo', price:180,   vendor:'NTT Data' },
    { desc:'NGFW Appliance Palo Alto PA-220',      cat:'Cybersecurity',     unit:'/device',  price:5200,  vendor:'CDW'      },
    { desc:'ZTNA Zero Trust Network Access',       cat:'Cybersecurity',     unit:'/user/mo', price:12,    vendor:'Zscaler'  },
    { desc:'SD-WAN Professional Services',         cat:'Service Management',unit:'/site',    price:2800,  vendor:'NTT Data' },
    { desc:'Network Monitoring & Reporting',       cat:'Network & Telecom', unit:'/site/mo', price:380,   vendor:'NTT Data' },
  ],
  'Cybersecurity': [
    { desc:'EDR - CrowdStrike Falcon',              cat:'Cybersecurity', unit:'/ep/yr',    price:180,   vendor:'CDW'      },
    { desc:'SIEM - Splunk Enterprise',              cat:'Cybersecurity', unit:'/yr',       price:48000, vendor:'NTT Data' },
    { desc:'Vulnerability Management - Tenable.io', cat:'Cybersecurity', unit:'/asset/yr', price:45,    vendor:'CDW'      },
    { desc:'PAM - CyberArk',                       cat:'IaAM',          unit:'/user/yr',  price:185,   vendor:'NTT Data' },
    { desc:'MFA - Okta',                           cat:'IaAM',          unit:'/user/mo',  price:8.5,   vendor:'CDW'      },
    { desc:'Web Application Firewall (WAF)',        cat:'Cybersecurity', unit:'/domain/mo',price:1200,  vendor:'NTT Data' },
    { desc:'Penetration Testing Annual',            cat:'Cybersecurity', unit:'/yr',       price:22000, vendor:'NTT Data' },
    { desc:'Security Awareness Training KnowBe4',  cat:'Cybersecurity', unit:'/user/yr',  price:28,    vendor:'CDW'      },
    { desc:'Incident Response Retainer 40hrs',      cat:'Cybersecurity', unit:'/yr',       price:18500, vendor:'NTT Data' },
  ],
  'Network Equipment': [
    { desc:'Cisco Catalyst 9300 48P PoE+ Switch', cat:'Network & Telecom',  unit:'/unit',    price:7800,  vendor:'CDW'           },
    { desc:'Cisco ASR 1001-X Core Router',        cat:'Network & Telecom',  unit:'/unit',    price:12500, vendor:'CDW'           },
    { desc:'Cisco Meraki MX85 Security Appliance',cat:'Cybersecurity',      unit:'/unit',    price:3900,  vendor:'CDW'           },
    { desc:'Fiber Optic Patch Panel 24-Port',     cat:'Network & Telecom',  unit:'/unit',    price:380,   vendor:'PC Connection' },
    { desc:'Network Rack Cabinet 42U with PDU',   cat:'Hosting',           unit:'/unit',    price:1950,  vendor:'PC Connection' },
    { desc:'UPS Power Backup 3kVA',               cat:'Hosting',           unit:'/unit',    price:2400,  vendor:'PC Connection' },
    { desc:'Cisco SmartNet Support 5Y NBD',        cat:'Service Management',unit:'/unit/yr', price:1850,  vendor:'CDW'           },
    { desc:'Installation & Commissioning',         cat:'Service Management',unit:'/site',    price:4500,  vendor:'NTT Data'      },
  ],
  'M365 & Power Platform': [
    { desc:'Microsoft 365 E3 License',          cat:'M365 & Power Platform', unit:'/user/mo', price:36,    vendor:'CDW'      },
    { desc:'M365 E5 Security Add-on',           cat:'M365 & Power Platform', unit:'/user/mo', price:12,    vendor:'CDW'      },
    { desc:'Power BI Premium Capacity',         cat:'M365 & Power Platform', unit:'/mo',      price:4995,  vendor:'CDW'      },
    { desc:'Power Apps Per-App Plan',           cat:'M365 & Power Platform', unit:'/user/mo', price:10,    vendor:'CDW'      },
    { desc:'SharePoint Intranet Setup',         cat:'M365 & Power Platform', unit:'/impl',    price:15000, vendor:'NTT Data' },
    { desc:'Teams Direct Routing (PSTN)',       cat:'M365 & Power Platform', unit:'/user/mo', price:18,    vendor:'NTT Data' },
    { desc:'Azure Active Directory P2',         cat:'IaAM',                  unit:'/user/mo', price:9,     vendor:'CDW'      },
    { desc:'M365 Migration & Onboarding',       cat:'Service Management',    unit:'/user',    price:85,    vendor:'NTT Data' },
  ],
  'Cloud Infrastructure': [
    { desc:'Azure ExpressRoute 1Gbps metered',  cat:'Network & Telecom', unit:'/ckt/mo', price:8500,  vendor:'NTT Data'   },
    { desc:'Azure Virtual WAN Hub',             cat:'Network & Telecom', unit:'/mo',     price:3200,  vendor:'NTT DOCOMO' },
    { desc:'Azure Backup 100TB Vault',          cat:'Hosting',           unit:'/mo',     price:2100,  vendor:'NTT DOCOMO' },
    { desc:'Azure Sentinel SIEM 500GB/day',     cat:'Cybersecurity',     unit:'/mo',     price:4200,  vendor:'NTT DOCOMO' },
    { desc:'Azure Defender for Cloud',          cat:'Cybersecurity',     unit:'/srv/mo', price:15,    vendor:'Microsoft'  },
    { desc:'Azure IAM & Conditional Access',    cat:'IaAM',              unit:'/mo',     price:2400,  vendor:'Microsoft'  },
    { desc:'Cloud Governance & Landing Zone',   cat:'Service Management',unit:'/impl',   price:45000, vendor:'NTT Data'   },
    { desc:'Cloud FinOps & Cost Management',    cat:'Service Management',unit:'/mo',     price:3500,  vendor:'NTT Data'   },
  ],
}

const CATEGORIES = Object.keys(TEMPLATES)
const PROJECTS = ['Panasonic', 'Idemia', 'Tenneco']

function detectCategory(msg) {
  const m = msg.toLowerCase()
  if (m.match(/data.?cent|colo/)) return 'Data Center / COLO'
  if (m.match(/sd.?wan|wan|branch/)) return 'SD-WAN'
  if (m.match(/cyber|security|siem|edr|firewall|soc/)) return 'Cybersecurity'
  if (m.match(/network equip|switch|router|cisco cat|asr|patch/)) return 'Network Equipment'
  if (m.match(/m365|365|office|teams|sharepoint|power.?bi/)) return 'M365 & Power Platform'
  if (m.match(/cloud|azure|aws|expressroute|landing zone/)) return 'Cloud Infrastructure'
  return null
}
function detectProject(msg) {
  const m = msg.toLowerCase()
  if (m.includes('panasonic')) return 'Panasonic'
  if (m.includes('idemia')) return 'Idemia'
  if (m.includes('tenneco')) return 'Tenneco'
  return null
}
function extractQty(msg) {
  const m = msg.match(/(\d+)\s*(site|rack|server|device|user|node|location)/i)
  return m ? parseInt(m[1]) : 1
}
function buildBOM(project, category, qty = 1) {
  const items = TEMPLATES[category] || TEMPLATES['Data Center / COLO']
  const lineItems = items.map((t, i) => ({
    id: 'li_' + Date.now() + '_' + i, lineNo: i + 1,
    category: t.cat, description: t.desc, unit: t.unit,
    qty, unitPrice: t.price, extPrice: t.price * qty,
    vendor: t.vendor, status: 'draft',
  }))
  const total = lineItems.reduce((s, i) => s + i.extPrice, 0)
  return {
    id: 'bom_draft_' + Date.now(),
    name: project + ' - ' + category,
    project, category, status: 'draft', version: 1,
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    createdBy: 'AI Chat', lineItems, totalValue: total,
    history: [{ version: 1, timestamp: new Date().toISOString(), action: 'Created via AI Chat', changes: lineItems.length + ' services generated', user: 'AI Assistant', totalValue: total }],
  }
}

const fmt = (v) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v)

function exportBOMasCSV(bom) {
  const headers = ['Line No', 'Description', 'Category', 'Unit', 'Qty', 'Unit Price (USD)', 'Ext Price (USD)', 'Vendor', 'Status']
  const rows = bom.lineItems.map(i => [
    i.lineNo,
    '"' + i.description.replace(/"/g, '""') + '"',
    '"' + i.category.replace(/"/g, '""') + '"',
    '"' + i.unit.replace(/"/g, '""') + '"',
    i.qty,
    i.unitPrice,
    i.extPrice,
    '"' + i.vendor.replace(/"/g, '""') + '"',
    i.status,
  ])
  const summaryRow = ['', '', '', '', 'TOTAL', '', bom.totalValue, '', '']
  const csv = [headers.join(','), ...rows.map(r => r.join(',')), summaryRow.join(',')].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = bom.name.replace(/[^a-zA-Z0-9 _-]/g, '') + '_BOM.csv'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function getAIResponse(userMsg, currentBOM, bomList, ctx) {
  const msg = userMsg.toLowerCase().trim()
  const cat = detectCategory(msg)
  const proj = detectProject(msg)
  const qty = extractQty(msg)

  if (msg.match(/^(save|confirm|done|ok|yes|looks good|perfect|approve)/)) {
    if (currentBOM) return {
      type: 'saved',
      text: 'BOM **"' + currentBOM.name + '"** saved to the BOM Library with **' + currentBOM.lineItems.length + ' line items** totalling **' + fmt(currentBOM.totalValue) + '**.\n\nYou can view it in the BOM Library or send it to RFQ Builder.',
      bom: currentBOM, actions: ['library', 'rfq'],
    }
    return { type: 'text', text: "No active BOM to save. Try: Create a Data Center BOM for Panasonic" }
  }

  if (msg.match(/rfq|send to rfq/)) {
    if (currentBOM) return { type: 'rfq', text: 'BOM **"' + currentBOM.name + '"** is ready for the RFQ Builder.', bom: currentBOM, actions: ['rfq'] }
  }

  // Add item to BOM: "add [qty]x [description] from [vendor]" or "add [description]"
  const addMatch = msg.match(/^add\s+(?:(\d+)\s*x\s+)?(.+?)(?:\s+from\s+([\w\s]+?))?(?:\s+at\s+\$?([\d,]+))?$/i)
  if (addMatch && currentBOM) {
    const addQty = parseInt(addMatch[1]) || 1
    const addDesc = addMatch[2].trim()
    const addVendor = addMatch[3]?.trim() || 'CDW'
    const addPrice = parseFloat((addMatch[4] || '').replace(/,/g, '')) || 0
    const newItem = {
      id: 'li_' + Date.now(),
      lineNo: currentBOM.lineItems.length + 1,
      category: detectCategory(addDesc) || 'Network & Telecom',
      description: addDesc.charAt(0).toUpperCase() + addDesc.slice(1),
      unit: '/unit', qty: addQty, unitPrice: addPrice, extPrice: addPrice * addQty,
      vendor: addVendor, status: 'draft',
    }
    const newItems = [...currentBOM.lineItems, newItem]
    const newBOM = { ...currentBOM, lineItems: newItems, totalValue: newItems.reduce((s, i) => s + i.extPrice, 0), updatedAt: new Date().toISOString() }
    return {
      type: 'updated',
      text: 'Added **Item ' + newItem.lineNo + '**: ' + newItem.description + ' (qty: ' + addQty + ', vendor: ' + addVendor + (addPrice ? ', price: ' + fmt(addPrice) : '') + ').\n\nBOM now has **' + newItems.length + ' items**' + (addPrice ? ' - revised total: **' + fmt(newBOM.totalValue) + '**' : ' - set the price by saying: Change item ' + newItem.lineNo + ' price to $XXXX'),
      bom: newBOM,
    }
  }
  if (msg.match(/^add\s+/i) && !currentBOM) {
    return { type: 'text', text: 'Please create or load a BOM first, then I can add items to it. Try: Create a Data Center BOM for Panasonic' }
  }

  // Update price of item N
  const priceMatch = msg.match(/(?:change|update|set)\s+(?:item\s+)?(\d+)\s+(?:price|unit.?price)\s+(?:to|=)\s+\$?([\d,]+)/i)
  if (priceMatch && currentBOM) {
    const lineNo = parseInt(priceMatch[1])
    const newPrice = parseFloat(priceMatch[2].replace(/,/g, '')) || 0
    const item = currentBOM.lineItems.find(i => i.lineNo === lineNo)
    if (item) {
      const updated = { ...item, unitPrice: newPrice, extPrice: newPrice * item.qty }
      const newItems = currentBOM.lineItems.map(i => i.lineNo === lineNo ? updated : i)
      const newBOM = { ...currentBOM, lineItems: newItems, totalValue: newItems.reduce((s, i) => s + i.extPrice, 0), updatedAt: new Date().toISOString() }
      return { type: 'updated', text: 'Updated **Item ' + lineNo + '** (' + item.description + '): unit price set to **' + fmt(newPrice) + '**. Line total: **' + fmt(updated.extPrice) + '**\n\nRevised BOM total: **' + fmt(newBOM.totalValue) + '**', bom: newBOM }
    }
  }

  if (msg.match(/export|download|csv/)) {
    if (currentBOM) {
      exportBOMasCSV(currentBOM)
      return { type: 'text', text: 'Exported **"' + currentBOM.name + '"** as CSV with all ' + currentBOM.lineItems.length + ' line items (Line No, Description, Category, Unit, Qty, Unit Price, Ext Price, Vendor, Status).' }
    }
    return { type: 'text', text: 'Please load or create a BOM first, then I can export it.' }
  }

  if (msg.match(/analyz|insight|saving|cost|cheaper|break.?down|summary/)) {
    if (!currentBOM) return { type: 'text', text: 'Please create or load a BOM first, then I can analyze it.' }
    const cats = currentBOM.lineItems.reduce((a, i) => { a[i.category] = (a[i.category] || 0) + i.extPrice; return a }, {})
    const topCat = Object.entries(cats).sort((a, b) => b[1] - a[1])[0]
    const vendors = [...new Set(currentBOM.lineItems.map(i => i.vendor))]
    return {
      type: 'analysis',
      text: 'Analysis: **' + currentBOM.name + '**\n\nTotal: **' + fmt(currentBOM.totalValue) + '** | ' + currentBOM.lineItems.length + ' services | ' + vendors.length + ' vendors',
      breakdown: cats,
      insights: [
        'Highest spend: ' + (topCat?.[0] || '') + ' at ' + fmt(topCat?.[1] || 0) + ' (' + (((topCat?.[1] || 0) / currentBOM.totalValue) * 100).toFixed(0) + '% of total)',
        'Vendor concentration: ' + vendors.slice(0, 2).join(', ') + ' - consider alternate quotes for cost reduction',
        'Quick win: Request volume discount for quantities over 10 on recurring monthly services',
        currentBOM.lineItems.filter(i => i.status === 'draft').length + ' items still in draft status - review before sending to RFQ',
      ],
    }
  }

  const qtyMatch = msg.match(/(?:change|update|set)\s+(?:item\s+)?(\d+)\s+(?:qty|quantity)\s+(?:to|=)\s+(\d+)/i)
  if (qtyMatch && currentBOM) {
    const lineNo = parseInt(qtyMatch[1])
    const newQty = parseInt(qtyMatch[2])
    const item = currentBOM.lineItems.find(i => i.lineNo === lineNo)
    if (item) {
      const updated = { ...item, qty: newQty, extPrice: item.unitPrice * newQty }
      const newItems = currentBOM.lineItems.map(i => i.lineNo === lineNo ? updated : i)
      const newBOM = { ...currentBOM, lineItems: newItems, totalValue: newItems.reduce((s, i) => s + i.extPrice, 0), updatedAt: new Date().toISOString() }
      return { type: 'updated', text: 'Updated **Item ' + lineNo + '** (' + item.description + '): qty ' + item.qty + ' -> ' + newQty + '. Line total: **' + fmt(updated.extPrice) + '**\n\nRevised BOM total: **' + fmt(newBOM.totalValue) + '**', bom: newBOM }
    }
  }

  const vendorMatch = msg.match(/(?:change|update|set)\s+(?:item\s+)?(\d+)\s+vendor\s+(?:to)?\s+([\w\s]+)/i)
  if (vendorMatch && currentBOM) {
    const lineNo = parseInt(vendorMatch[1])
    const newVendor = vendorMatch[2].trim()
    const item = currentBOM.lineItems.find(i => i.lineNo === lineNo)
    if (item) {
      const newItems = currentBOM.lineItems.map(i => i.lineNo === lineNo ? { ...i, vendor: newVendor } : i)
      const newBOM = { ...currentBOM, lineItems: newItems, updatedAt: new Date().toISOString() }
      return { type: 'updated', text: 'Updated **Item ' + lineNo + '** (' + item.description + '): vendor ' + item.vendor + ' -> ' + newVendor, bom: newBOM }
    }
  }

  const removeMatch = msg.match(/(?:remove|delete|drop)\s+(?:item\s+)?(\d+)/i)
  if (removeMatch && currentBOM) {
    const lineNo = parseInt(removeMatch[1])
    const item = currentBOM.lineItems.find(i => i.lineNo === lineNo)
    if (item) {
      const newItems = currentBOM.lineItems.filter(i => i.lineNo !== lineNo).map((i, idx) => ({ ...i, lineNo: idx + 1 }))
      const newBOM = { ...currentBOM, lineItems: newItems, totalValue: newItems.reduce((s, i) => s + i.extPrice, 0), updatedAt: new Date().toISOString() }
      return { type: 'updated', text: 'Removed **Item ' + lineNo + '**: ' + item.description + '. BOM now has **' + newItems.length + ' items** totalling **' + fmt(newBOM.totalValue) + '**.', bom: newBOM }
    }
  }

  if (msg.match(/show|list|my bom|all bom|existing bom/)) {
    if (bomList.length === 0) return { type: 'text', text: 'No saved BOMs yet. Try: Create a SD-WAN BOM for Panasonic with 20 sites' }
    return { type: 'bom_list', text: 'Your **' + bomList.length + ' saved BOMs**:', boms: bomList.slice(0, 6) }
  }

  const loadMatch = bomList.find(b =>
    msg.includes(b.name.toLowerCase()) ||
    msg.includes(b.project.toLowerCase() + ' ' + b.category.toLowerCase().split('/')[0].trim())
  )
  if (loadMatch && msg.match(/load|open|edit|update|show me/)) {
    return {
      type: 'loaded',
      text: 'Loaded **"' + loadMatch.name + '"** (v' + loadMatch.version + ') - **' + loadMatch.lineItems.length + ' items**, ' + fmt(loadMatch.totalValue) + '.\n\nYou can now:\n- Change item 3 qty to 8\n- Remove item 6\n- Analyze this BOM\n- Export as CSV\n- Save',
      bom: loadMatch,
    }
  }

  if (msg.match(/create|build|new bom|generate|need|setup|make|prepare/) || cat || proj) {
    if (!proj && !ctx.project) {
      return { type: 'options', text: 'Which **project** is this BOM for?', field: 'project', options: PROJECTS.map(p => ({ label: p, action: 'project:' + p })) }
    }
    if (!cat && !ctx.category) {
      const project = proj || ctx.project
      return { type: 'options', text: 'Creating BOM for **' + project + '**. What type of services?', field: 'category', options: CATEGORIES.map(c => ({ label: c, action: 'category:' + c })) }
    }
    const project = proj || ctx.project || 'New Project'
    const category = cat || ctx.category || 'Data Center / COLO'
    const bom = buildBOM(project, category, qty)
    return {
      type: 'bom_created',
      text: 'Created BOM: **"' + bom.name + '"**\n\n**' + bom.lineItems.length + ' services** auto-populated from industry templates.\nEstimated total: **' + fmt(bom.totalValue) + '**\n\nThe BOM is live in the right panel.\n\nWhat you can do:\n- Change item 4 qty to 8\n- Remove item 7\n- Change item 2 vendor to CDW\n- Analyze this BOM\n- Save (to BOM Library)\n- Export as CSV',
      bom,
    }
  }

  return {
    type: 'help',
    text: 'I am your **AI BOM Assistant**. I can help you:\n\n- **Create** BOMs: Create a Data Center BOM for Panasonic with 8 racks\n- **Add items**: Add 5x Cisco Catalyst 9300 from CDW at $7800\n- **Update** items: Change item 3 qty to 15 | Change item 2 price to $4500 | Remove item 6\n- **Change vendor**: Change item 4 vendor to NTT Data\n- **Analyze**: Analyze cost savings on this BOM\n- **Load**: Load Panasonic SD-WAN BOM\n- **Show all**: Show my BOMs\n- **Export**: Export as CSV\n- **Save & send**: Save | Send to RFQ',
    suggestions: [
      'Create a Data Center BOM for Panasonic',
      'Add 10x Cisco Catalyst 9300 from CDW at $7800',
      'Create Cybersecurity BOM for Idemia',
      'Show my BOMs',
    ],
  }
}

// Convert backend BOM (snake_case line_items) to frontend BOM (camelCase lineItems)
function backendBOMtoFrontend(backendBOM, projectName) {
  if (!backendBOM || !backendBOM.line_items) return null
  const lineItems = backendBOM.line_items.map((item, i) => ({
    id: 'li_ai_' + Date.now() + '_' + i,
    lineNo: item.line_number || i + 1,
    category: item.category || 'General',
    description: item.description || '',
    unit: item.unit || '/unit',
    qty: item.qty || 1,
    unitPrice: item.unit_price || 0,
    extPrice: item.extended_price || (item.unit_price || 0) * (item.qty || 1),
    vendor: item.vendor || '',
    status: item.eol_flag ? 'eol_flagged' : 'draft',
    sku: item.sku || '',
    term: item.term || 'one-time',
    orderSeq: item.order_sequence || '',
    notes: item.notes || '',
  }))
  const totalValue = lineItems.reduce((s, i) => s + i.extPrice, 0)
  return {
    id: 'bom_ai_' + Date.now(),
    name: backendBOM.name || (projectName + ' BOM'),
    project: backendBOM.project || projectName || 'New Project',
    category: backendBOM.category || 'Data Center / COLO',
    status: 'draft', version: 1,
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    createdBy: 'AI Agent',
    lineItems, totalValue,
    warnings: backendBOM.warnings || [],
    approvalsRequired: backendBOM.approvals_required || ['Buyer IT', 'Seller IT', 'SI Technical Team'],
    history: [{ version: 1, timestamp: new Date().toISOString(), action: 'Generated by AI Agent', changes: lineItems.length + ' line items', user: 'AI Assistant', totalValue }],
  }
}

// Export BOM as Excel via backend, fall back to CSV
async function exportBOMExcel(bom, dispatchFn) {
  try {
    const bomId = bom.id || 'chat_bom'
    const backendPayload = {
      name: bom.name, project: bom.project, category: bom.category,
      status: bom.status, version: bom.version, created_at: bom.createdAt,
      line_items: bom.lineItems.map(i => ({
        line_number: i.lineNo, category: i.category, description: i.description,
        sku: i.sku || '', qty: i.qty, unit: i.unit, unit_price: i.unitPrice,
        extended_price: i.extPrice, vendor: i.vendor, term: i.term || 'one-time',
        eol_flag: i.status === 'eol_flagged', order_sequence: i.orderSeq || '',
      })),
      totals: { total_otc: bom.totalValue, hardware: 0, software: 0, services: 0, tco_3year: 0 },
      warnings: bom.warnings || [],
    }
    const blob = await bomApi.exportChatBOMExcel(bomId, backendPayload)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = bom.name.replace(/[^a-zA-Z0-9 _-]/g, '') + '_BOM.xlsx'
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    // Fallback to CSV
    exportBOMasCSV(bom)
  }
}

export default function ChatPage() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const bomList = useSelector(s => s.bom.bomList)
  const savedCurrentBOM = useSelector(s => s.bom.currentBOM)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [currentBOM, setLocalBOM] = useState(savedCurrentBOM || null)
  const [ctx, setCtx] = useState({ project: null, category: null })
  const msgEndRef = useRef(null)

  // Backend AI state
  const [sessionId, setSessionId]       = useState(null)
  const [backendMode, setBackendMode]   = useState(false)
  const [phaseProgress, setPhaseProgress] = useState(0)
  const [backendChecked, setBackendChecked] = useState(false)
  const [toast, setToast] = useState({ open: false, msg: '', severity: 'info' })

  // Derive current phase (1-10) from progress percentage
  const currentPhase = phaseProgress > 0 ? Math.max(1, Math.min(10, Math.ceil(phaseProgress / 10))) : 0
  const phaseName = PHASE_NAMES[currentPhase] || ''
  const phaseChips = PHASE_CHIPS[currentPhase] || []

  // Check if backend is available on mount
  useEffect(() => {
    chatApi.ping().then(online => {
      setBackendMode(online)
      setBackendChecked(true)
    })
  }, [])

  useEffect(() => {
    const welcome = savedCurrentBOM
      ? { id: 1, role: 'ai', type: 'loaded', text: 'Loaded **"' + savedCurrentBOM.name + '"** (v' + savedCurrentBOM.version + ') - **' + savedCurrentBOM.lineItems.length + ' items**, ' + fmt(savedCurrentBOM.totalValue) + '. What would you like to do?', bom: savedCurrentBOM }
      : { id: 1, role: 'ai', type: 'help', text: 'Hello! I am your **AI BOM Assistant**.\n\nI can create, update, analyze and manage your Bills of Materials in real-time. Just describe what you need in plain English.', suggestions: ['Create a Data Center BOM for Panasonic', 'Create SD-WAN BOM for 30 sites', 'Create Cybersecurity BOM for Idemia', 'Show my BOMs'] }
    setMessages([welcome])
    if (savedCurrentBOM) setLocalBOM(savedCurrentBOM)
  }, [])

  useEffect(() => { msgEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isTyping])

  const addMsg = (msg) => setMessages(prev => [...prev, { ...msg, id: Date.now() + Math.random() }])

  const handleSend = useCallback(async (text) => {
    const userText = (text || input).trim()
    if (!userText) return
    setInput('')
    addMsg({ role: 'user', type: 'text', text: userText })
    setIsTyping(true)

    // ── Try backend AI first ──────────────────────────────────────────────
    if (backendMode) {
      try {
        let sid = sessionId
        // Start a session if we don't have one yet
        if (!sid) {
          const cat  = detectCategory(userText) || ctx.category || 'Data Center / COLO'
          const proj = detectProject(userText) || ctx.project || 'New Project'
          const startResp = await chatApi.startSession(cat, proj)
          sid = startResp.session_id
          setSessionId(sid)
          // Show the welcome message from backend
          setIsTyping(false)
          addMsg({ role: 'ai', type: 'text', text: startResp.message })
          setIsTyping(true)
        }
        let resp
        try {
          resp = await chatApi.sendMessage(sid, userText)
        } catch (sendErr) {
          // Session may have expired — reset and retry once
          if (sendErr?.response?.status === 404 || sendErr?.response?.status === 422) {
            setSessionId(null)
            const cat  = detectCategory(userText) || ctx.category || 'Data Center / COLO'
            const proj = detectProject(userText) || ctx.project || 'New Project'
            const startResp = await chatApi.startSession(cat, proj)
            sid = startResp.session_id
            setSessionId(sid)
            resp = await chatApi.sendMessage(sid, userText)
          } else {
            throw sendErr
          }
        }
        setIsTyping(false)
        setPhaseProgress(resp.progress || 0)

        // If BOM was generated by AI, convert and show it
        let aiBOM = null
        if (resp.partial_bom) {
          const proj = detectProject(userText) || ctx.project || 'New Project'
          aiBOM = backendBOMtoFrontend(resp.partial_bom, proj)
          if (aiBOM) { setLocalBOM(aiBOM); dispatch(setCurrentBOM(aiBOM)) }
        }

        // Auto-save to backend when BOM is complete
        if (resp.complete && aiBOM) {
          try {
            await bomApi?.create?.(aiBOM)
            dispatch(saveBOM(aiBOM))
            setToast({ open: true, msg: 'BOM saved to library automatically', severity: 'success' })
          } catch { /* save is best-effort */ }
        }

        addMsg({
          role: 'ai',
          type: resp.complete ? 'bom_created' : 'text',
          text: resp.response,
          bom: aiBOM,
        })
        return
      } catch (err) {
        // Backend call failed — fall through to local logic
        console.warn('Backend AI unavailable, falling back to local:', err?.message)
        setBackendMode(false)
        setToast({ open: true, msg: 'AI backend unavailable — using local mode', severity: 'warning' })
      }
    }

    // ── Local rule-based fallback ─────────────────────────────────────────
    setTimeout(() => {
      setIsTyping(false)
      const resp = getAIResponse(userText, currentBOM, bomList, ctx)
      if (resp.bom) { setLocalBOM(resp.bom); dispatch(setCurrentBOM(resp.bom)) }
      if (resp.type === 'saved' && resp.bom) dispatch(saveBOM(resp.bom))
      addMsg({ role: 'ai', ...resp })
    }, 600 + Math.random() * 400)
  }, [input, backendMode, sessionId, currentBOM, bomList, ctx, dispatch])

  const handleOption = (action) => {
    if (action.startsWith('project:')) {
      const project = action.replace('project:', '')
      setCtx(c => ({ ...c, project }))
      handleSend(project + ' project')
    } else if (action.startsWith('category:')) {
      const category = action.replace('category:', '')
      setCtx(c => ({ ...c, category }))
      handleSend(category)
    }
  }

  const renderText = (text) => text.split('\n').map((line, i) => {
    const parts = line.split(/\*\*(.+?)\*\*/)
    return (
      <Typography key={i} sx={{ fontSize: '0.78rem', lineHeight: 1.6, color: 'inherit' }}>
        {parts.map((p, j) => j % 2 === 1 ? <strong key={j}>{p}</strong> : p)}
        {i < text.split('\n').length - 1 && <br />}
      </Typography>
    )
  })

  const isAI = (m) => m.role === 'ai'

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 44px)', bgcolor: '#F9FAFB', overflow: 'hidden' }}>

      {/* Left: BOM Sessions */}
      <Box sx={{ width: 220, flexShrink: 0, bgcolor: 'white', borderRight: '1px solid #F3F4F6', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 1.25, borderBottom: '1px solid #F3F4F6' }}>
          <Button fullWidth variant="contained" size="small" startIcon={<Add sx={{ fontSize: 14 }} />}
            onClick={() => {
              setLocalBOM(null)
              dispatch(setCurrentBOM(null))
              setCtx({})
              setSessionId(null)
              setPhaseProgress(0)
              setMessages([{ id: Date.now(), role: 'ai', type: 'help', text: 'New session started. What BOM would you like to create?', suggestions: ['Create Data Center BOM for Panasonic', 'Create SD-WAN for 20 sites'] }])
            }}
            sx={{ textTransform: 'none', fontSize: '0.72rem', fontWeight: 700, bgcolor: '#D04A02', '&:hover': { bgcolor: '#A33A00' } }}>
            New BOM Chat
          </Button>
        </Box>
        <Box sx={{ p: 1, pb: 0.5 }}>
          <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.7px' }}>Saved BOMs</Typography>
        </Box>
        <Box sx={{ flex: 1, overflowY: 'auto', px: 1 }}>
          {bomList.slice(0, 8).map(bom => (
            <Box key={bom.id}
              onClick={() => handleSend('Load ' + bom.name)}
              sx={{ p: 1, mb: 0.5, borderRadius: '6px', cursor: 'pointer', border: '1px solid #F3F4F6', bgcolor: currentBOM?.id === bom.id ? '#FDF3ED' : 'white', '&:hover': { bgcolor: '#F9FAFB' } }}>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: currentBOM?.id === bom.id ? '#D04A02' : '#1F2937', lineHeight: 1.2, mb: 0.2 }} noWrap>{bom.name}</Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Chip label={bom.status} size="small" sx={{ fontSize: '0.55rem', height: 14, bgcolor: bom.status === 'active' ? '#D1FAE5' : '#FEF3C7', color: bom.status === 'active' ? '#065F46' : '#92400E' }} />
                <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF' }}>v{bom.version}</Typography>
              </Box>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Center: Chat */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <Box sx={{ flexShrink: 0, bgcolor: 'white', borderBottom: '1px solid #F3F4F6' }}>
          <Box sx={{ height: 44, display: 'flex', alignItems: 'center', px: 2, gap: 1.5 }}>
            <AutoAwesome sx={{ fontSize: 18, color: '#D04A02' }} />
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#1F2937', lineHeight: 1 }}>AI BOM Assistant</Typography>
              <Typography sx={{ fontSize: '0.6rem', color: '#9CA3AF' }}>Create - Update - Analyze - Export</Typography>
            </Box>
            {backendChecked && (
              <Tooltip title={backendMode ? 'AI Backend connected — 10-phase BOM methodology active' : 'Backend offline — using local templates'}>
                <Chip
                  icon={backendMode ? <CloudDone sx={{ fontSize: '12px !important' }} /> : <CloudOff sx={{ fontSize: '12px !important' }} />}
                  label={backendMode ? 'AI Active' : 'Local Mode'}
                  size="small"
                  sx={{ fontSize: '0.58rem', height: 18, cursor: 'default',
                    bgcolor: backendMode ? '#D1FAE5' : '#FEF3C7',
                    color: backendMode ? '#065F46' : '#92400E',
                    '& .MuiChip-icon': { color: 'inherit' },
                  }}
                />
              </Tooltip>
            )}
          </Box>
          {backendMode && phaseProgress > 0 && (
            <Box sx={{ px: 2, pb: 0.75 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <Typography sx={{ fontSize: '0.58rem', fontWeight: 700, color: '#0369A1', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Phase {currentPhase}</Typography>
                  {phaseName && <Typography sx={{ fontSize: '0.58rem', color: '#6B7280' }}>— {phaseName}</Typography>}
                </Box>
                <Typography sx={{ fontSize: '0.58rem', color: '#0369A1' }}>{phaseProgress}%</Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={phaseProgress}
                sx={{ height: 3, borderRadius: 2, bgcolor: '#E0F2FE', '& .MuiLinearProgress-bar': { bgcolor: phaseProgress === 100 ? '#10B981' : '#0284C7', borderRadius: 2 } }}
              />
            </Box>
          )}
        </Box>

        <Box sx={{ flex: 1, overflowY: 'auto', p: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {messages.map(msg => (
            <Box key={msg.id} sx={{ display: 'flex', justifyContent: isAI(msg) ? 'flex-start' : 'flex-end', alignItems: 'flex-start', gap: 0.75 }}>
              {isAI(msg) && (
                <Avatar sx={{ width: 26, height: 26, bgcolor: '#D04A02', flexShrink: 0 }}>
                  <AutoAwesome sx={{ fontSize: 13 }} />
                </Avatar>
              )}
              <Box sx={{ maxWidth: '80%' }}>
                <Box sx={{
                  bgcolor: isAI(msg) ? 'white' : '#D04A02',
                  color: isAI(msg) ? '#1F2937' : 'white',
                  border: isAI(msg) ? '1px solid #F3F4F6' : 'none',
                  borderRadius: isAI(msg) ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
                  p: 1.25, boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                }}>
                  {renderText(msg.text)}

                  {msg.options && (
                    <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {msg.options.map(opt => (
                        <Chip key={opt.action} label={opt.label} size="small" onClick={() => handleOption(opt.action)}
                          sx={{ fontSize: '0.68rem', height: 22, cursor: 'pointer', bgcolor: '#FDF3ED', color: '#D04A02', fontWeight: 600, border: '1px solid #FBBF9F', '&:hover': { bgcolor: '#D04A02', color: 'white' } }} />
                      ))}
                    </Box>
                  )}

                  {msg.suggestions && (
                    <Box sx={{ mt: 1 }}>
                      <Typography sx={{ fontSize: '0.62rem', color: '#9CA3AF', mb: 0.5 }}>Try asking:</Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
                        {msg.suggestions.map(s => (
                          <Box key={s} onClick={() => handleSend(s)}
                            sx={{ fontSize: '0.7rem', color: '#3B82F6', cursor: 'pointer', p: '4px 8px', borderRadius: '4px', bgcolor: '#EFF6FF', '&:hover': { bgcolor: '#DBEAFE' } }}>
                            {s}
                          </Box>
                        ))}
                      </Box>
                    </Box>
                  )}

                  {msg.boms && (
                    <Box sx={{ mt: 1 }}>
                      {msg.boms.map(b => (
                        <Box key={b.id} onClick={() => handleSend('Load ' + b.name)}
                          sx={{ display: 'flex', justifyContent: 'space-between', p: '4px 8px', borderRadius: 1, mb: 0.4, bgcolor: '#F9FAFB', cursor: 'pointer', '&:hover': { bgcolor: '#F3F4F6' } }}>
                          <Typography sx={{ fontSize: '0.68rem', fontWeight: 600 }}>{b.name}</Typography>
                          <Typography sx={{ fontSize: '0.65rem', color: '#D04A02', fontWeight: 700 }}>{fmt(b.totalValue)}</Typography>
                        </Box>
                      ))}
                    </Box>
                  )}

                  {msg.breakdown && (
                    <Box sx={{ mt: 1 }}>
                      {Object.entries(msg.breakdown).sort((a, b) => b[1] - a[1]).map(([cat, val]) => (
                        <Box key={cat} sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.4 }}>
                          <Typography sx={{ fontSize: '0.65rem', flex: 1 }} noWrap>{cat}</Typography>
                          <Box sx={{ width: 80, height: 5, bgcolor: '#F3F4F6', borderRadius: 1, overflow: 'hidden' }}>
                            <Box sx={{ width: ((val / (currentBOM?.totalValue || 1)) * 100) + '%', height: '100%', bgcolor: '#D04A02' }} />
                          </Box>
                          <Typography sx={{ fontSize: '0.65rem', fontWeight: 700, minWidth: 52, textAlign: 'right' }}>{fmt(val)}</Typography>
                        </Box>
                      ))}
                      {msg.insights && (
                        <Box sx={{ mt: 0.75, bgcolor: '#F9FAFB', borderRadius: 1, p: 1 }}>
                          {msg.insights.map((ins, i) => (
                            <Typography key={i} sx={{ fontSize: '0.68rem', lineHeight: 1.7, color: '#374151' }}>{ins}</Typography>
                          ))}
                        </Box>
                      )}
                    </Box>
                  )}

                  {msg.actions && (
                    <Box sx={{ mt: 1, display: 'flex', gap: 0.75 }}>
                      {msg.actions.includes('library') && (
                        <Button size="small" variant="outlined" startIcon={<FolderOpen sx={{ fontSize: 12 }} />}
                          onClick={() => navigate('/bom-library')}
                          sx={{ fontSize: '0.65rem', py: 0.3, textTransform: 'none', borderColor: '#D04A02', color: '#D04A02' }}>
                          View in Library
                        </Button>
                      )}
                      {msg.actions.includes('rfq') && (
                        <Button size="small" variant="contained" startIcon={<Build sx={{ fontSize: 12 }} />}
                          onClick={() => { if (currentBOM) dispatch(setActiveBOMForRFQ(currentBOM)); navigate('/rfq-builder') }}
                          sx={{ fontSize: '0.65rem', py: 0.3, textTransform: 'none', bgcolor: '#3B82F6', '&:hover': { bgcolor: '#1D4ED8' } }}>
                          Send to RFQ
                        </Button>
                      )}
                    </Box>
                  )}
                </Box>
              </Box>
              {!isAI(msg) && (
                <Avatar sx={{ width: 26, height: 26, bgcolor: '#374151', flexShrink: 0 }}>
                  <Person sx={{ fontSize: 13 }} />
                </Avatar>
              )}
            </Box>
          ))}

          {isTyping && (
            <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
              <Avatar sx={{ width: 26, height: 26, bgcolor: '#D04A02' }}><AutoAwesome sx={{ fontSize: 13 }} /></Avatar>
              <Paper sx={{ px: 1.5, py: 1, border: '1px solid #F3F4F6' }}>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  {[0, 1, 2].map(i => (
                    <Box key={i} sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#9CA3AF',
                      animation: 'bounce 1s ' + (i * 0.15) + 's infinite',
                      '@keyframes bounce': { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-4px)' } },
                    }} />
                  ))}
                </Box>
              </Paper>
            </Box>
          )}
          <div ref={msgEndRef} />
        </Box>

        <Box sx={{ p: 1.5, bgcolor: 'white', borderTop: '1px solid #F3F4F6' }}>
          {/* Phase-specific quick chips */}
          {phaseChips.length > 0 && (
            <Box sx={{ mb: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {phaseChips.map(chip => (
                <Chip key={chip} label={chip} size="small" onClick={() => handleSend(chip)}
                  sx={{ fontSize: '0.65rem', height: 20, cursor: 'pointer', bgcolor: '#F0F9FF', color: '#0369A1',
                    border: '1px solid #BAE6FD', '&:hover': { bgcolor: '#0369A1', color: 'white' } }} />
              ))}
            </Box>
          )}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
            <TextField
              multiline maxRows={4} fullWidth
              placeholder="Ask me to create, update, or analyze a BOM..."
              value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              sx={{ bgcolor: '#F9FAFB', '& .MuiInputBase-input': { fontSize: '0.8rem', py: '8px' }, '& .MuiOutlinedInput-root': { '& fieldset': { borderColor: '#E5E7EB' }, '&:hover fieldset': { borderColor: '#D04A02' }, '&.Mui-focused fieldset': { borderColor: '#D04A02' } } }}
            />
            <IconButton onClick={() => handleSend()} disabled={!input.trim() || isTyping}
              sx={{ width: 40, height: 40, bgcolor: '#D04A02', color: 'white', borderRadius: '8px', flexShrink: 0, '&:hover': { bgcolor: '#A33A00' }, '&.Mui-disabled': { bgcolor: '#F3F4F6', color: '#9CA3AF' } }}>
              <Send sx={{ fontSize: 18 }} />
            </IconButton>
          </Box>
          <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF', mt: 0.5, textAlign: 'center' }}>
            Press Enter to send | Shift+Enter for new line
          </Typography>
        </Box>
      </Box>

      {/* Right: Live BOM Preview */}
      <Box sx={{ width: 300, flexShrink: 0, bgcolor: 'white', borderLeft: '1px solid #F3F4F6', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ p: 1.25, borderBottom: '1px solid #F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.75rem', color: '#1F2937' }}>
            {currentBOM ? 'Live BOM Preview' : 'BOM Preview'}
          </Typography>
          {currentBOM && (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title="Save BOM"><IconButton size="small" onClick={() => handleSend('save')} sx={{ color: '#10B981' }}><Save sx={{ fontSize: 15 }} /></IconButton></Tooltip>
              <Tooltip title="Send to RFQ"><IconButton size="small" onClick={() => { dispatch(setActiveBOMForRFQ(currentBOM)); navigate('/rfq-builder') }} sx={{ color: '#3B82F6' }}><Build sx={{ fontSize: 15 }} /></IconButton></Tooltip>
              <Tooltip title="Export as Excel"><IconButton size="small" onClick={() => exportBOMExcel(currentBOM, dispatch)} sx={{ color: '#6B7280' }}><Download sx={{ fontSize: 15 }} /></IconButton></Tooltip>
            </Box>
          )}
        </Box>

        {!currentBOM ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', p: 2, textAlign: 'center' }}>
            <AutoAwesome sx={{ fontSize: 32, color: '#E5E7EB', mb: 1 }} />
            <Typography sx={{ fontSize: '0.75rem', color: '#9CA3AF', lineHeight: 1.5 }}>
              Your BOM will appear here as you build it in the chat
            </Typography>
            <Typography sx={{ fontSize: '0.65rem', color: '#C4C9D0', mt: 0.5 }}>
              Try: Create a Data Center BOM for Panasonic
            </Typography>
          </Box>
        ) : (
          <>
            <Box sx={{ px: 1.5, pt: 1.25, pb: 0.75, borderBottom: '1px solid #F9FAFB' }}>
              <Typography sx={{ fontWeight: 700, fontSize: '0.78rem', color: '#1F2937', lineHeight: 1.2 }}>{currentBOM.name}</Typography>
              <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5, flexWrap: 'wrap' }}>
                <Chip label={currentBOM.status} size="small" sx={{ fontSize: '0.58rem', height: 16, bgcolor: currentBOM.status === 'active' ? '#D1FAE5' : '#FEF3C7', color: currentBOM.status === 'active' ? '#065F46' : '#92400E' }} />
                <Chip label={'v' + currentBOM.version} size="small" sx={{ fontSize: '0.58rem', height: 16, bgcolor: '#F3F4F6', color: '#374151' }} />
                <Chip label={currentBOM.lineItems.length + ' items'} size="small" sx={{ fontSize: '0.58rem', height: 16, bgcolor: '#DBEAFE', color: '#1E40AF' }} />
              </Box>
            </Box>

            <Box sx={{ flex: 1, overflowY: 'auto', px: 1.25, py: 0.75 }}>
              {currentBOM.lineItems.map(item => (
                <Box key={item.id} sx={{ display: 'flex', gap: 0.75, py: 0.6, borderBottom: '1px solid #F9FAFB', alignItems: 'flex-start' }}>
                  <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF', fontWeight: 700, minWidth: 14, pt: 0.2 }}>{item.lineNo}</Typography>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.68rem', fontWeight: 500, lineHeight: 1.25, color: '#1F2937' }} noWrap>{item.description}</Typography>
                    <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF' }}>{item.vendor} - qty {item.qty} - {item.unit}</Typography>
                  </Box>
                  <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#374151', flexShrink: 0 }}>
                    {fmt(item.extPrice)}
                  </Typography>
                </Box>
              ))}
            </Box>

            <Box sx={{ p: 1.25, borderTop: '1px solid #F3F4F6', bgcolor: '#FAFAFA' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: '#1F2937' }}>Total Value</Typography>
                <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: '"Playfair Display", serif', color: '#D04A02' }}>
                  {fmt(currentBOM.totalValue)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.75, mb: 0.75 }}>
                <Button fullWidth size="small" variant="contained" onClick={() => handleSend('save')}
                  sx={{ textTransform: 'none', fontSize: '0.68rem', fontWeight: 700, bgcolor: '#D04A02', '&:hover': { bgcolor: '#A33A00' }, py: 0.5 }}>
                  Save BOM
                </Button>
                <Button fullWidth size="small" variant="outlined" onClick={() => { dispatch(setActiveBOMForRFQ(currentBOM)); navigate('/rfq-builder') }}
                  sx={{ textTransform: 'none', fontSize: '0.68rem', fontWeight: 700, borderColor: '#3B82F6', color: '#3B82F6', py: 0.5 }}>
                  RFQ
                </Button>
              </Box>
              <Button fullWidth size="small" variant="outlined"
                startIcon={<Download sx={{ fontSize: 13 }} />}
                onClick={() => exportBOMExcel(currentBOM, dispatch)}
                sx={{ textTransform: 'none', fontSize: '0.68rem', fontWeight: 600, borderColor: '#E5E7EB', color: '#6B7280', py: 0.4 }}>
                Export Excel ({currentBOM.lineItems.length} items)
              </Button>
              <Button fullWidth size="small" variant="outlined"
                startIcon={<RateReview sx={{ fontSize: 13 }} />}
                onClick={() => navigate('/bom-review')}
                sx={{ mt: 0.5, textTransform: 'none', fontSize: '0.68rem', fontWeight: 600, borderColor: '#8B5CF6', color: '#8B5CF6', py: 0.4 }}>
                Send to Review
              </Button>
            </Box>
          </>
        )}
      </Box>

      {/* Toast notifications */}
      <Snackbar open={toast.open} autoHideDuration={4000}
        onClose={() => setToast(t => ({ ...t, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity={toast.severity} onClose={() => setToast(t => ({ ...t, open: false }))} sx={{ fontSize: '0.8rem' }}>
          {toast.msg}
        </Alert>
      </Snackbar>
    </Box>
  )
}

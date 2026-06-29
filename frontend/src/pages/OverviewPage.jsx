import { useState } from 'react'
import { useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Typography,
  Box,
  Grid,
  Card,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  Button,
  AlertTitle,
  Collapse,
  IconButton,
} from '@mui/material'
import { ExpandMore, ExpandLess, Warning, Error as ErrorIcon, Info } from '@mui/icons-material'
import { Bar } from 'react-chartjs-2'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const projects = [
  { name: 'Idemia', files: 9, categories: 3, services: 32, vendors: 4, totalSpend: 122.62, avgQuote: 57.85, bestPrice: 310, color: '#D04A02', timeline: [30, 45, 25] },
  { name: 'Panasonic', files: 31, categories: 5, services: 75, vendors: 8, totalSpend: 331.40, avgQuote: 60.69, bestPrice: 504, color: '#10B981', timeline: [20, 35, 45] },
  { name: 'Tenneco', files: 8, categories: 2, services: 22, vendors: 4, totalSpend: 244, avgQuote: 309, bestPrice: 126, color: '#3B82F6', timeline: [40, 35, 25] },
]

const categories = [
  { name: 'Network & Telecom', color: '#1F2937', files: 18, services: 49, vendors: 4, priceMin: 77, priceMax: 99630, avg: 31120, volatility: 3497 },
  { name: 'Cybersecurity', color: '#D04A02', files: 10, services: 25, vendors: 4, priceMin: 1320, priceMax: 45000, avg: 7630, volatility: 327 },
  { name: 'Hosting', color: '#3B82F6', files: 7, services: 18, vendors: 5, priceMin: 1230, priceMax: 32000, avg: 6640, volatility: 3045 },
  { name: 'M365 & Power Platform', color: '#8B5CF6', files: 5, services: 24, vendors: 3, priceMin: 890, priceMax: 28000, avg: 5880, volatility: 231 },
  { name: 'IaAM', color: '#F59E0B', files: 6, services: 11, vendors: 2, priceMin: 500, priceMax: 12000, avg: 2080, volatility: 117 },
  { name: 'Service Management (SNow)', color: '#10B981', files: 2, services: 5, vendors: 1, priceMin: 1200, priceMax: 4500, avg: 990, volatility: 23 },
]

const heatmapData = [
  { vendor: 'NTT Data', Cybersecurity: 2.51, Hosting: 2.98, IaAM: null, 'M365 & PP': null, 'Network & Telecom': 202.83, 'Svc Mgmt': null, total: 268.32 },
  { vendor: 'CDW', Cybersecurity: null, Hosting: null, IaAM: null, 'M365 & PP': null, 'Network & Telecom': 175.41, 'Svc Mgmt': null, total: 175.41 },
  { vendor: 'PC Connection', Cybersecurity: null, Hosting: null, IaAM: null, 'M365 & PP': null, 'Network & Telecom': 131.90, 'Svc Mgmt': null, total: 131.90 },
  { vendor: 'Equinix', Cybersecurity: null, Hosting: 5.12, IaAM: null, 'M365 & PP': null, 'Network & Telecom': 26.08, 'Svc Mgmt': null, total: 31.20 },
  { vendor: 'NTT DOCOMO', Cybersecurity: null, Hosting: 24.39, IaAM: null, 'M365 & PP': null, 'Network & Telecom': null, 'Svc Mgmt': null, total: 24.39 },
]
const heatmapCols = ['Cybersecurity', 'Hosting', 'IaAM', 'M365 & PP', 'Network & Telecom', 'Svc Mgmt']

const vendorConcentration = [
  { rank: 1, vendor: 'NTT Data', quotes: 16, categories: 3, spend: 268.32, percentage: 40.3 },
  { rank: 2, vendor: 'CDW', quotes: 8, categories: 2, spend: 175.41, percentage: 26.7 },
  { rank: 3, vendor: 'PC Connection', quotes: 12, categories: 2, spend: 131.90, percentage: 20.1 },
  { rank: 4, vendor: 'Equinix', quotes: 4, categories: 2, spend: 31.20, percentage: 4.8 },
  { rank: 5, vendor: 'NTT DOCOMO', quotes: 5, categories: 2, spend: 24.39, percentage: 3.7 },
]

const topServices = [
  { name: 'Global MPLS Network Premium', category: 'Network & Telecom', vendors: 15, quotes: 130, price: '$18.52M' },
  { name: 'Enterprise SOC-as-a-Service', category: 'Cybersecurity', vendors: 8, quotes: 62, price: '$9.84M' },
  { name: 'Colocation Tier-4 Full Rack', category: 'Hosting', vendors: 6, quotes: 44, price: '$6.21M' },
]

const chartOpts = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { bodyFont: { size: 10 }, titleFont: { size: 10 } } },
  scales: { x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 30 } }, y: { grid: { color: '#F3F4F6' }, beginAtZero: true, ticks: { font: { size: 9 } } } },
}
const chartOptsH = { ...chartOpts, indexAxis: 'y', scales: { x: { grid: { color: '#F3F4F6' }, beginAtZero: true, ticks: { font: { size: 9 } } }, y: { grid: { display: false }, ticks: { font: { size: 9 } } } } }
const SL = { color: '#1F2937', fontWeight: 700, letterSpacing: '0.6px', textTransform: 'uppercase', mb: 0.75, display: 'block', fontSize: '0.62rem' }

export default function OverviewPage() {
  const [selectedProject, setSelectedProject] = useState('All')
  const [region, setRegion] = useState('APAC')
  const [country, setCountry] = useState('All')
  const [dateRange, setDateRange] = useState('All')
  const [alertsOpen, setAlertsOpen] = useState(true)
  const navigate = useNavigate()
  const bomList = useSelector(s => s.bom?.bomList || [])

  // Derive live alerts from Redux BOM state
  const now = new Date()
  const alerts = []
  bomList.forEach(bom => {
    const updatedDays = Math.floor((now - new Date(bom.updatedAt)) / 86400000)
    if (bom.status === 'draft' && updatedDays > 30) alerts.push({ severity: 'warning', bom, msg: `"${bom.name}" has been a Draft for ${updatedDays} days — consider submitting for review.` })
    if (bom.status === 'review' && updatedDays > 7) alerts.push({ severity: 'error', bom, msg: `"${bom.name}" has been In Review for ${updatedDays} days — pending approval.` })
    if (bom.lineItems?.filter(i => i.status === 'quoted').length === 0 && bom.status !== 'archived') alerts.push({ severity: 'info', bom, msg: `"${bom.name}" has 0 quoted items — send to RFQ Builder to get vendor pricing.` })
  })

  const trimLabel = (s, n=12) => s.length > n ? s.slice(0,n)+'...' : s

  const charts = [
    { title: 'Categories vs Quote Volume', data: { labels: categories.map(c => trimLabel(c.name.split(' ')[0],8)), datasets: [{ data: categories.map(c=>c.files), backgroundColor: categories.map(c=>c.color), borderRadius:3 }] }, opts: chartOpts },
    { title: 'Services per Category', data: { labels: categories.map(c=>trimLabel(c.name)), datasets: [{ data: categories.map(c=>c.services), backgroundColor: categories.map(c=>c.color), borderRadius:3 }] }, opts: chartOptsH },
    { title: 'Vendors by Quote Volume', data: { labels: vendorConcentration.map(v=>trimLabel(v.vendor,11)), datasets: [{ data: vendorConcentration.map(v=>v.quotes), backgroundColor:'#D04A02', borderRadius:3 }] }, opts: chartOptsH },
    { title: 'Vendors by Avg Price Quoted', data: { labels: vendorConcentration.map(v=>trimLabel(v.vendor,11)), datasets: [{ data: vendorConcentration.map(v=>v.spend), backgroundColor:'#3B82F6', borderRadius:3 }] }, opts: chartOptsH },
  ]

  return (
    <Box sx={{ bgcolor: '#FAFAFA', minHeight: 'calc(100vh - 42px)', overflowX: 'hidden' }}>
      <Container maxWidth={false} disableGutters sx={{ py: 1.25, px: { xs: 1.5, lg: 2.5 } }}>

        {/* Header */}
        <Box sx={{ mb: 1.25, display: 'flex', alignItems: 'baseline', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Box sx={{ color: '#D04A02', fontWeight: 700, letterSpacing: '0.8px', textTransform: 'uppercase', fontSize: '0.6rem', lineHeight: 1 }}>
              EXECUTIVE DASHBOARD
            </Box>
            <Box sx={{ fontWeight: 700, color: '#1F2937', fontSize: '1.3rem', lineHeight: 1.15, fontFamily: '"Playfair Display", serif' }}>
              Portfolio Overview
            </Box>
          </Box>
          <Box sx={{ color: '#6B7280', fontWeight: 500, fontSize: '0.72rem' }}>
            Strategic view of vendor spend, service coverage and pricing intelligence
          </Box>
        </Box>

        {/* Alert Panel */}
        {alerts.length > 0 && (
          <Box sx={{ mb: 1.25 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Warning sx={{ fontSize: 14, color: '#F59E0B' }} />
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#92400E' }}>
                {alerts.length} BOM Alert{alerts.length > 1 ? 's' : ''} require attention
              </Typography>
              <IconButton size="small" onClick={() => setAlertsOpen(o => !o)} sx={{ ml: 'auto', p: 0.25 }}>
                {alertsOpen ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
              </IconButton>
            </Box>
            <Collapse in={alertsOpen}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {alerts.slice(0, 5).map((a, i) => (
                  <Alert key={i} severity={a.severity} sx={{ py: 0.25, fontSize: '0.7rem' }}
                    action={<Button size="small" onClick={() => navigate('/bom-library')} sx={{ fontSize: '0.6rem', textTransform: 'none' }}>View BOM</Button>}>
                    {a.msg}
                  </Alert>
                ))}
              </Box>
            </Collapse>
          </Box>
        )}

        {/* Filters row */}
        <Box sx={{ display: 'flex', gap: 0.6, mb: 1.25, flexWrap: 'wrap', alignItems: 'center' }}>
          {[{ label:'All', count:48 }, ...projects.map(p=>({label:p.name, count:p.files}))].map(({ label, count }) => (
            <Chip key={label} label={`${label} · ${count}`} size="small" onClick={() => setSelectedProject(label)}
              sx={{ bgcolor: selectedProject===label?'#1F2937':'white', color: selectedProject===label?'white':'#6B7280', fontWeight:700, fontSize:'0.68rem', cursor:'pointer', border:'1px solid #E5E7EB', height:24 }} />
          ))}
          <Box sx={{ flexGrow:1 }} />
          {['Last 30d', 'Last 90d', 'YTD', 'All'].map(r => (
            <Chip key={r} label={r} size="small" onClick={() => setDateRange(r)}
              sx={{ fontSize: '0.62rem', height: 22, cursor: 'pointer', bgcolor: dateRange === r ? '#1F2937' : 'white', color: dateRange === r ? 'white' : '#6B7280', border: '1px solid #E5E7EB', fontWeight: dateRange === r ? 700 : 400 }} />
          ))}
          {[['Region',region,setRegion,['APAC','Americas','EMEA'],110], ['Country',country,setCountry,['All Countries','United States','Germany'],130]].map(([lbl,val,setter,opts,w]) => (
            <FormControl key={lbl} size="small" sx={{ minWidth: w }}>
              <InputLabel sx={{ fontSize:'0.72rem' }}>{lbl}</InputLabel>
              <Select value={val} onChange={e=>setter(e.target.value)} label={lbl} sx={{ bgcolor:'white', fontSize:'0.72rem', '.MuiSelect-select':{py:'3px'} }}>
                {opts.map(o=><MenuItem key={o} value={o} sx={{ fontSize:'0.72rem' }}>{o}</MenuItem>)}
              </Select>
            </FormControl>
          ))}
        </Box>

        {/* PROJECT PORTFOLIO */}
        <Box sx={SL}>PROJECT PORTFOLIO · Click to drill in · each card shows full project snapshot</Box>
        <Grid container spacing={1.25} sx={{ mb: 1.75 }}>
          {projects.map(proj => (
            <Grid item xs={12} md={4} key={proj.name}>
              <Card sx={{ borderLeft:`5px solid ${proj.color}`, cursor:'pointer', '&:hover':{boxShadow:3} }}>
                <Box sx={{ p:1.25 }}>
                  <Box sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', mb:0.4 }}>
                    <Box sx={{ fontWeight:700, fontFamily:'"Playfair Display",serif', fontSize:'0.95rem', color:'#1F2937' }}>{proj.name}</Box>
                    <Chip label={`${proj.files} files`} size="small" sx={{ bgcolor:'#D04A02', color:'white', fontWeight:700, fontSize:'0.6rem', height:18 }} />
                  </Box>
                  <Box sx={{ color:'#6B7280', mb:0.75, fontSize:'0.67rem' }}>
                    {proj.categories} categories · {proj.services} services · {proj.vendors} vendors
                  </Box>
                  <Box sx={{ display:'flex', height:5, mb:0.4, borderRadius:1, overflow:'hidden' }}>
                    {proj.timeline.map((pct,i) => <Box key={i} sx={{ width:`${pct}%`, bgcolor:['#FFD4B3','#FFB380',proj.color][i] }} />)}
                  </Box>
                  <Box sx={{ display:'flex', justifyContent:'space-between', mb:0.75 }}>
                    {['2024','2025','2026'].map(y=><Box key={y} sx={{ color:'#9CA3AF', fontSize:'0.58rem' }}>{y}</Box>)}
                  </Box>
                  <Grid container spacing={0.75}>
                    {[['TOTAL SPEND',`$${proj.totalSpend}M`,'#1F2937'],['AVG QUOTE',`$${proj.avgQuote}M`,'#D04A02'],['BEST PRICE',`$${proj.bestPrice}K`,'#10B981']].map(([lbl,val,clr])=>(
                      <Grid item xs={4} key={lbl}>
                        <Box sx={{ fontWeight:700, fontFamily:'"Playfair Display",serif', fontSize:'0.9rem', color:clr, lineHeight:1.1 }}>{val}</Box>
                        <Box sx={{ color:'#6B7280', fontSize:'0.55rem', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.3px' }}>{lbl}</Box>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* AT A GLANCE */}
        <Box sx={SL}>AT A GLANCE · Simple metrics for quick understanding</Box>
        <Grid container spacing={1.25} sx={{ mb: 1.75 }}>
          {charts.map(({ title, data, opts }) => (
            <Grid item xs={12} sm={6} md={3} key={title}>
              <Paper sx={{ p:1.25, height:195 }}>
                <Box sx={{ color:'#6B7280', fontSize:'0.68rem', fontWeight:600, mb:0.6 }}>{title}</Box>
                <Box sx={{ height:158 }}>
                  <Bar data={data} options={opts} />
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>

        {/* SPEND TREEMAP + AVG QUOTE PRICE */}
        <Box sx={SL}>SPEND DISTRIBUTION · Visual breakdown of total spend by category</Box>
        <Grid container spacing={1.25} sx={{ mb: 1.75 }}>
          {/* Spend Treemap */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 1.5, height: 220 }}>
              <Box sx={{ display:'flex', alignItems:'center', gap:0.75, mb:1 }}>
                <Box sx={{ color:'#3B82F6', fontSize:'0.85rem' }}>▦</Box>
                <Box sx={{ fontWeight:700, fontSize:'0.78rem' }}>Spend Treemap</Box>
              </Box>
              <Box sx={{ display:'flex', flexDirection:'column', gap:0.5, height:158 }}>
                {/* Row 1: top 5 categories proportional width */}
                <Box sx={{ display:'flex', gap:0.5, flex:'0 0 60%' }}>
                  {[
                    { name:'Network & Telecom', value:'$396.22M', pct:'90.8%', color:'#1F2937', flex:9.08 },
                    { name:'Hosting', value:'$46.48M', pct:'7.1%', color:'#3B82F6', flex:0.71 },
                    { name:'Cybersecurity', value:'$7.63M', pct:'1.2%', color:'#D04A02', flex:0.12 },
                    { name:'M365 & Power\nPlatform', value:'$2.93M', pct:'0.4%', color:'#8B5CF6', flex:0.04 },
                    { name:'Service\nManagement\n(SNow)', value:'$1.98M', pct:'0.3%', color:'#10B981', flex:0.03 },
                  ].map(t=>(
                    <Box key={t.name} sx={{
                      flex: t.flex, bgcolor: t.color, borderRadius:1, p: t.flex > 1 ? '6px 8px' : '4px',
                      display:'flex', flexDirection:'column', justifyContent:'flex-end', overflow:'hidden', cursor:'pointer',
                      '&:hover': { filter:'brightness(1.15)' }, transition:'filter 0.15s',
                      minWidth: t.flex < 0.1 ? 32 : 'auto',
                    }}>
                      {t.flex > 0.5 && <Box sx={{ color:'white', fontSize:'0.6rem', fontWeight:600, mb:0.25, lineHeight:1.2, opacity:0.85 }}>{t.name}</Box>}
                      {t.flex > 0.5 && <Box sx={{ color:'white', fontWeight:800, fontSize: t.flex > 1 ? '0.95rem' : '0.65rem', fontFamily:'"Playfair Display",serif', lineHeight:1.1 }}>{t.value}</Box>}
                      {t.flex > 0.5 && <Box sx={{ color:'rgba(255,255,255,0.7)', fontSize:'0.55rem', fontWeight:600 }}>{t.pct} of total</Box>}
                    </Box>
                  ))}
                </Box>
                {/* Row 2: IaAM full width */}
                <Box sx={{
                  flex:'1', bgcolor:'#F59E0B', borderRadius:1, p:'6px 10px',
                  display:'flex', alignItems:'center', gap:2, cursor:'pointer',
                  '&:hover':{ filter:'brightness(1.1)' }, transition:'filter 0.15s',
                }}>
                  <Box sx={{ color:'white', fontSize:'0.72rem', fontWeight:600 }}>IaAM</Box>
                  <Box sx={{ color:'white', fontWeight:800, fontSize:'1rem', fontFamily:'"Playfair Display",serif' }}>$1.25M</Box>
                  <Box sx={{ color:'rgba(255,255,255,0.8)', fontSize:'0.62rem' }}>0.2% of total</Box>
                </Box>
              </Box>
            </Paper>
          </Grid>

          {/* Avg Quote Price by Category */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p:1.5, height:220 }}>
              <Box sx={{ display:'flex', alignItems:'center', gap:0.75, mb:1 }}>
                <Box sx={{ color:'#F59E0B', fontSize:'0.85rem' }}>📊</Box>
                <Box sx={{ fontWeight:700, fontSize:'0.78rem' }}>Average Quote Price by Category</Box>
              </Box>
              <Box sx={{ height:160 }}>
                <Bar
                  data={{
                    labels: ['Network & Telecom','Hosting','Service Mgmt','Cybersecurity','M365 & Power...','IaAM'],
                    datasets:[{
                      data: [31120000, 6640000, 990000, 7630000, 5880000, 2080000],
                      backgroundColor: ['#1F2937','#3B82F6','#10B981','#D04A02','#8B5CF6','#F59E0B'],
                      borderRadius: 3,
                    }],
                  }}
                  options={{
                    responsive:true, maintainAspectRatio:false, indexAxis:'y',
                    plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label: ctx => ` $${(ctx.raw/1000000).toFixed(2)}M` }, bodyFont:{size:10}, titleFont:{size:10} } },
                    scales:{
                      x:{ grid:{color:'#F3F4F6'}, beginAtZero:true, ticks:{ font:{size:8.5}, callback: v => `$${(v/1000000).toFixed(0)}M` } },
                      y:{ grid:{display:false}, ticks:{font:{size:8.5}} },
                    },
                  }}
                />
              </Box>
            </Paper>
          </Grid>
        </Grid>

        {/* DETAILED INSIGHTS */}
        <Box sx={SL}>DETAILED INSIGHTS · Deeper analysis for strategic decisions</Box>
        <Paper sx={{ p:1.5, mb:1.75 }}>
          <Box sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', mb:0.75 }}>
            <Box sx={{ fontWeight:700, fontSize:'0.78rem' }}>🔥 Vendor × Category Spend Heatmap</Box>
            <Box sx={{ display:'flex', gap:0.5 }}>
              <Button size="small" variant="outlined" sx={{ fontSize:'0.65rem', py:0.2, px:0.75, minWidth:0 }}>All</Button>
              <Button size="small" variant="outlined" sx={{ fontSize:'0.65rem', py:0.2, px:0.75, minWidth:0 }}>Clear</Button>
            </Box>
          </Box>
          <Grid container spacing={1} sx={{ mb:0.75 }}>
            <Grid item xs={12} sm={5}>
              <Box sx={{ color:'#6B7280', fontWeight:700, fontSize:'0.58rem', textTransform:'uppercase', letterSpacing:'0.5px', mb:0.4 }}>🟦 VENDORS</Box>
              <Box sx={{ display:'flex', flexWrap:'wrap', gap:0.35 }}>
                {['NTT Data 16','CDW 8','PC Connection 12','Equinix 4','NTT DOCOMO 5'].map(v=>(
                  <Chip key={v} label={v} size="small" sx={{ bgcolor:'#D04A02', color:'white', fontWeight:700, fontSize:'0.58rem', height:16 }} />
                ))}
                <Chip label="ALL" size="small" sx={{ color:'#D04A02', fontWeight:700, fontSize:'0.58rem', height:16 }} />
              </Box>
            </Grid>
            <Grid item xs={12} sm={7}>
              <Box sx={{ color:'#6B7280', fontWeight:700, fontSize:'0.58rem', textTransform:'uppercase', letterSpacing:'0.5px', mb:0.4 }}>🟩 CATEGORIES</Box>
              <Box sx={{ display:'flex', flexWrap:'wrap', gap:0.35 }}>
                {['Cybersecurity 16','Hosting 7','IaAM 9','M365 5','Network 16','Svc Mgmt 2'].map(c=>(
                  <Chip key={c} label={c} size="small" sx={{ bgcolor:'#D04A02', color:'white', fontWeight:700, fontSize:'0.58rem', height:16 }} />
                ))}
                <Chip label="ALL" size="small" sx={{ color:'#D04A02', fontWeight:700, fontSize:'0.58rem', height:16 }} />
              </Box>
            </Grid>
          </Grid>
          <TableContainer sx={{ border:'1px solid #E5E7EB', borderRadius:1 }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor:'#1F2937' }}>
                  <TableCell sx={{ color:'white', fontWeight:700, fontSize:'0.65rem', minWidth:120, position:'sticky', left:0, bgcolor:'#1F2937', zIndex:2, py:0.6 }}>Vendor</TableCell>
                  {heatmapCols.map(col=>(
                    <TableCell key={col} sx={{ color:'white', fontWeight:700, textAlign:'center', fontSize:'0.62rem', py:0.6 }}>{col}</TableCell>
                  ))}
                  <TableCell sx={{ color:'white', fontWeight:700, textAlign:'right', fontSize:'0.65rem', py:0.6 }}>Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {heatmapData.map(row=>(
                  <TableRow key={row.vendor} sx={{ '&:hover':{bgcolor:'#FFF7F0'} }}>
                    <TableCell sx={{ fontWeight:600, fontSize:'0.68rem', position:'sticky', left:0, bgcolor:'#FAFAFA', borderRight:'1px solid #E5E7EB', py:0.4 }}>{row.vendor}</TableCell>
                    {heatmapCols.map(col=>(
                      <TableCell key={col} sx={{ textAlign:'center', fontSize:'0.68rem', py:0.4, bgcolor:row[col]?'#FFE5D0':'#FAFAFA', fontWeight:row[col]?700:400, color:row[col]?'#1F2937':'#CBD5E1', cursor:row[col]?'pointer':'default' }}>
                        {row[col]?`$${row[col]}M`:'—'}
                      </TableCell>
                    ))}
                    <TableCell sx={{ textAlign:'right', fontWeight:700, fontSize:'0.68rem', py:0.4 }}>${row.total}M</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>

        {/* Category Deep-Dive + Vendor Concentration */}
        <Grid container spacing={1.25} sx={{ mb: 1.5 }}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p:1.5, height:'100%' }}>
              <Box sx={{ fontWeight:700, fontSize:'0.78rem', mb:0.75 }}>📊 Category Deep-Dive</Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor:'#F3F4F6' }}>
                      {['CATEGORY','FILES','SERVICES','VENDORS','PRICE RANGE','AVG','VOLATILITY'].map(h=>(
                        <TableCell key={h} align={h==='CATEGORY'?'left':'right'} sx={{ fontWeight:700, fontSize:'0.58rem', textTransform:'uppercase', py:0.4, letterSpacing:'0.2px' }}>{h}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {categories.map(cat=>(
                      <TableRow key={cat.name} sx={{ '&:hover':{bgcolor:'#F9FAFB'} }}>
                        <TableCell sx={{ py:0.35 }}>
                          <Box sx={{ display:'flex', alignItems:'center', gap:0.6 }}>
                            <Box sx={{ width:6, height:6, borderRadius:'1px', bgcolor:cat.color, flexShrink:0 }} />
                            <Box sx={{ fontWeight:600, fontSize:'0.68rem' }}>{cat.name}</Box>
                          </Box>
                        </TableCell>
                        <TableCell align="right" sx={{ fontSize:'0.68rem', py:0.35 }}>{cat.files}</TableCell>
                        <TableCell align="right" sx={{ fontSize:'0.68rem', py:0.35 }}>{cat.services}</TableCell>
                        <TableCell align="right" sx={{ fontSize:'0.68rem', py:0.35 }}>{cat.vendors}</TableCell>
                        <TableCell align="right" sx={{ py:0.35 }}>
                          <Box sx={{ display:'flex', alignItems:'center', gap:0.4, justifyContent:'flex-end' }}>
                            <Box sx={{ width:32, height:4, background:'linear-gradient(90deg,#10B981,#F59E0B,#EF4444)', borderRadius:1 }} />
                            <Box sx={{ fontSize:'0.6rem', fontWeight:600 }}>${cat.priceMin}–${(cat.priceMax/1000).toFixed(0)}K</Box>
                          </Box>
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight:600, fontSize:'0.68rem', py:0.35 }}>${cat.avg.toLocaleString()}</TableCell>
                        <TableCell align="right" sx={{ py:0.35 }}>
                          <Box sx={{ display:'flex', alignItems:'center', gap:0.4, justifyContent:'flex-end' }}>
                            <Box sx={{ width:24, height:4, bgcolor:'#EF4444', borderRadius:1 }} />
                            <Box sx={{ fontWeight:700, color:'#EF4444', fontSize:'0.62rem' }}>{cat.volatility}%</Box>
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          <Grid item xs={12} md={4}>
            <Paper sx={{ p:1.5, mb:1.25 }}>
              <Box sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', mb:0.6 }}>
                <Box sx={{ fontWeight:700, fontSize:'0.78rem' }}>📍 Vendor Concentration Risk</Box>
                <Chip label="15 vendors" size="small" sx={{ bgcolor:'#10B981', color:'white', fontWeight:700, fontSize:'0.58rem', height:16 }} />
              </Box>
              <Alert severity="error" sx={{ mb:1, py:0.4, '& .MuiAlert-message':{py:0} }}>
                <Box sx={{ fontWeight:700, fontSize:'0.65rem', lineHeight:1.3 }}>⚠️ HIGH CONCENTRATION</Box>
                <Box sx={{ fontSize:'0.62rem' }}>Top 5 vendors = 96.1% of total spend</Box>
              </Alert>
              {vendorConcentration.map(v=>(
                <Box key={v.vendor} sx={{ mb:0.75 }}>
                  <Box sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', mb:0.25 }}>
                    <Box sx={{ display:'flex', alignItems:'center', gap:0.4 }}>
                      <Box sx={{ fontWeight:700, color:'#6B7280', fontSize:'0.62rem', minWidth:8 }}>{v.rank}</Box>
                      <Chip label={v.vendor} size="small" sx={{ bgcolor:'#D04A02', color:'white', fontWeight:700, fontSize:'0.58rem', height:16 }} />
                    </Box>
                    <Box sx={{ fontWeight:700, fontSize:'0.68rem' }}>${v.spend}M</Box>
                  </Box>
                  <Box sx={{ display:'flex', alignItems:'center', gap:0.6 }}>
                    <Box sx={{ flexGrow:1, height:4, bgcolor:'#E5E7EB', borderRadius:1, overflow:'hidden' }}>
                      <Box sx={{ width:`${v.percentage}%`, height:'100%', bgcolor:'#D04A02' }} />
                    </Box>
                    <Box sx={{ fontWeight:700, fontSize:'0.62rem', minWidth:30, textAlign:'right' }}>{v.percentage}%</Box>
                  </Box>
                  <Box sx={{ color:'#6B7280', fontSize:'0.58rem' }}>{v.quotes} quotes · {v.categories} categories</Box>
                </Box>
              ))}
            </Paper>

            <Paper sx={{ p:1.5 }}>
              <Box sx={{ fontWeight:700, fontSize:'0.78rem', mb:0.75 }}>💰 Top Services by Avg Price</Box>
              {topServices.map((svc,i)=>(
                <Box key={i} sx={{ display:'flex', justifyContent:'space-between', alignItems:'center', p:0.75, bgcolor:'#F9FAFB', borderRadius:1, mb:0.6 }}>
                  <Box sx={{ flex:1, mr:1 }}>
                    <Box sx={{ fontWeight:600, fontSize:'0.68rem', lineHeight:1.2 }}>{svc.name}</Box>
                    <Box sx={{ color:'#6B7280', fontSize:'0.58rem' }}>{svc.category} · {svc.vendors} vendors · {svc.quotes} quotes</Box>
                  </Box>
                  <Box sx={{ fontWeight:700, fontFamily:'"Playfair Display",serif', fontSize:'0.85rem', color:'#D04A02', whiteSpace:'nowrap' }}>{svc.price}</Box>
                </Box>
              ))}
            </Paper>
          </Grid>
        </Grid>

      </Container>
    </Box>
  )
}

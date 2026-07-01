import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Box, Tooltip, IconButton, Chip, Button, Typography, Divider } from '@mui/material'
import {
  Dashboard as DashboardIcon,
  CompareArrows as CompareIcon,
  Receipt as ReceiptIcon,
  Build as BuildIcon,
  AutoAwesome as ChatIcon,
  LibraryBooks as LibraryIcon,
  Analytics as AnalyticsIcon,
  FileDownload, Refresh, ChevronLeft, ChevronRight,
} from '@mui/icons-material'

const NAV_W = 220
const NAV_C = 52

const menuItems = [
  { text: 'Overview', icon: <DashboardIcon sx={{ fontSize: 17 }} />, path: '/overview' },
  { text: 'Analytics', icon: <AnalyticsIcon sx={{ fontSize: 17 }} />, path: '/analytics' },
  { text: 'BOM Library', icon: <LibraryIcon sx={{ fontSize: 17 }} />, path: '/bom-library' },
  { text: 'AI BOM Assistant', icon: <ChatIcon sx={{ fontSize: 17 }} />, path: '/chat' },
  { text: 'Vendor Price Selector', icon: <CompareIcon sx={{ fontSize: 17 }} />, path: '/vendor-selector' },
  { text: 'Quote Extractor', icon: <ReceiptIcon sx={{ fontSize: 17 }} />, path: '/quote-extractor' },
  { text: 'RFQ Builder', icon: <BuildIcon sx={{ fontSize: 17 }} />, path: '/rfq-builder' },
]

export default function Layout({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ── Light Sidebar ── */}
      <Box sx={{
        width: collapsed ? NAV_C : NAV_W,
        flexShrink: 0,
        bgcolor: '#FFFFFF',
        borderRight: '1px solid #E5E7EB',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        overflow: 'hidden',
        position: 'relative',
        zIndex: 100,
      }}>

        {/* PwC Logo */}
        <Box sx={{
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: collapsed ? 0 : 1.25,
          px: collapsed ? 0 : 1.5, py: 1.25,
          minHeight: 56, flexShrink: 0,
          borderBottom: '1px solid #F3F4F6',
        }}>
          <Typography
            onClick={() => navigate('/overview')}
            sx={{
              fontFamily: '"Playfair Display", Georgia, serif',
              fontWeight: 800, color: '#D04A02',
              fontSize: collapsed ? '1.1rem' : '1.65rem',
              letterSpacing: '-1px', lineHeight: 1, cursor: 'pointer',
              flexShrink: 0, whiteSpace: 'nowrap',
            }}
          >
            {collapsed ? 'pw' : 'pwc'}
          </Typography>
          {!collapsed && (
            <>
              <Box sx={{ width: 1, height: 26, bgcolor: '#E5E7EB', flexShrink: 0 }} />
              <Box sx={{ overflow: 'hidden', flex: 1 }}>
                <Typography sx={{ fontWeight: 700, fontSize: '0.7rem', color: '#1F2937', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
                  IT Contracting
                </Typography>
                <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF', whiteSpace: 'nowrap' }}>
                  Intelligence Platform
                </Typography>
              </Box>
            </>
          )}
        </Box>

        {/* Nav section label */}
        {!collapsed && (
          <Box sx={{ px: 1.75, pt: 1.25, pb: 0.5 }}>
            <Typography sx={{ fontSize: '0.55rem', fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
              Navigation
            </Typography>
          </Box>
        )}

        {/* Nav items */}
        <Box sx={{ flex: 1, pb: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          {menuItems.map(item => {
            const active = location.pathname === item.path || (location.pathname === '/' && item.path === '/overview')
            const el = (
              <Box
                key={item.path}
                onClick={() => navigate(item.path)}
                sx={{
                  display: 'flex', alignItems: 'center',
                  gap: 1.25,
                  px: collapsed ? 0 : 1.5, py: 0.85,
                  mx: 0.6, mb: 0.2, borderRadius: '6px',
                  cursor: 'pointer',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  bgcolor: active ? '#FDF3ED' : 'transparent',
                  borderLeft: !collapsed && active ? '3px solid #D04A02' : '3px solid transparent',
                  '&:hover': { bgcolor: active ? '#FDF3ED' : '#F9FAFB' },
                  transition: 'background 0.12s',
                }}
              >
                <Box sx={{ color: active ? '#D04A02' : '#6B7280', display: 'flex', flexShrink: 0, minWidth: 17 }}>
                  {item.icon}
                </Box>
                {!collapsed && (
                  <Typography sx={{
                    fontSize: '0.75rem', fontWeight: active ? 700 : 500,
                    color: active ? '#D04A02' : '#374151',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    lineHeight: 1.3,
                  }}>
                    {item.text}
                  </Typography>
                )}
              </Box>
            )
            return collapsed
              ? <Tooltip key={item.path} title={item.text} placement="right" arrow>{el}</Tooltip>
              : el
          })}
        </Box>

        {/* Bottom: status + collapse */}
        <Box sx={{ borderTop: '1px solid #F3F4F6', p: 1 }}>
          {!collapsed && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75, px: 0.5 }}>
              <Box sx={{
                width: 6, height: 6, bgcolor: '#10B981', borderRadius: '50%', flexShrink: 0,
                animation: 'pulse 2s infinite',
                '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
              }} />
              <Typography sx={{ fontSize: '0.58rem', color: '#9CA3AF' }}>48 Records · Demo Mode</Typography>
            </Box>
          )}
          <Tooltip title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} placement="right" arrow>
            <IconButton
              size="small"
              onClick={() => setCollapsed(!collapsed)}
              sx={{ width: '100%', borderRadius: '6px', py: 0.5, color: '#9CA3AF', '&:hover': { bgcolor: '#F3F4F6', color: '#374151' } }}
            >
              {collapsed ? <ChevronRight sx={{ fontSize: 17 }} /> : <ChevronLeft sx={{ fontSize: 17 }} />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Right: topbar + content ── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0, bgcolor: '#FAFAFA' }}>

        {/* Slim top bar */}
        <Box sx={{
          height: 44, flexShrink: 0,
          bgcolor: 'white', borderBottom: '1px solid #E5E7EB',
          display: 'flex', alignItems: 'center', px: 2, gap: 1.5,
        }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.78rem', color: '#6B7280', flex: 1 }}>
            Vendor Benchmarking &amp; Sourcing Platform
          </Typography>
          <Chip
            label="● Live Demo"
            size="small"
            sx={{ bgcolor: '#D1FAE5', color: '#065F46', fontWeight: 700, fontSize: '0.6rem', height: 22, '& .MuiChip-label': { px: 1 } }}
          />
          <Button size="small" variant="outlined" startIcon={<Refresh sx={{ fontSize: '13px !important' }} />}
            sx={{ textTransform: 'none', fontSize: '0.7rem', fontWeight: 600, color: '#374151', borderColor: '#E5E7EB', py: 0.3, '&:hover': { borderColor: '#D04A02', color: '#D04A02' } }}>
            Refresh
          </Button>
          <Button size="small" variant="contained" startIcon={<FileDownload sx={{ fontSize: '13px !important' }} />}
            sx={{ textTransform: 'none', fontSize: '0.7rem', fontWeight: 600, bgcolor: '#D04A02', py: 0.3, '&:hover': { bgcolor: '#A33A00' } }}>
            Export
          </Button>
        </Box>

        {/* Page content */}
        <Box component="main" sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          {children}
        </Box>
      </Box>
    </Box>
  )
}

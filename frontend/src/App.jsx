import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import OverviewPage from './pages/OverviewPage'
import BOMLibraryPage from './pages/BOMLibraryPage'
import ChatPage from './pages/ChatPage'
import VendorPriceSelectorPage from './pages/VendorPriceSelectorPage'
import QuoteExtractorPage from './pages/QuoteExtractorPage'
import RFQBuilderPage from './pages/RFQBuilderPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/bom-library" element={<BOMLibraryPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/vendor-selector" element={<VendorPriceSelectorPage />} />
        <Route path="/quote-extractor" element={<QuoteExtractorPage />} />
        <Route path="/rfq-builder" element={<RFQBuilderPage />} />
      </Routes>
    </Layout>
  )
}

export default App

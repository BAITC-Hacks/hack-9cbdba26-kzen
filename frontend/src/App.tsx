import { useState, useEffect } from 'react'
import type { AppHeader, RecommendationsPage, SkuId } from './types'
import { getSession, runCalculation, searchRecommendations } from './api/client'
import TopNav from './components/layout/TopNav'
import ContextBar from './components/layout/ContextBar'
import DataScreen from './screens/DataScreen'
import RecommendationsScreen from './screens/RecommendationsScreen'
import SkuScreen from './screens/SkuScreen'
import ReviewScreen from './screens/ReviewScreen'
import ValidationScreen from './screens/ValidationScreen'

export default function App() {
  const [screen, setScreen] = useState<1 | 2 | 3 | 4 | 5>(2)
  const [skuId, setSkuId] = useState<SkuId | null>(null)
  const [header, setHeader] = useState<AppHeader | null>(null)
  const [recommendations, setRecommendations] = useState<RecommendationsPage | null>(null)

  useEffect(() => {
    getSession().then(session => setHeader(current => current ?? session))
    searchRecommendations({}).then(d => {
      setRecommendations(d)
      setHeader(d.header)
    })
  }, [])

  function handleSkuClick(id: SkuId) {
    setSkuId(id)
    setScreen(3)
  }

  async function handleCalculate() {
    await runCalculation()
    const data = await searchRecommendations({})
    setRecommendations(data)
    setHeader(data.header)
    setScreen(2)
  }

  function openScreen(next: number) {
    if (next === 2 && !recommendations) {
      searchRecommendations({}).then(result => { setRecommendations(result); setHeader(result.header) })
    }
    setScreen(next as 1 | 2 | 3 | 4 | 5)
  }

  if (!header) {
    return (
      <div style={{ padding: 40, fontFamily: 'var(--font-body)', color: 'var(--color-neutral-600)' }}>
        Загрузка…
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopNav header={header} activeScreen={screen} onScreen={openScreen} />
      <ContextBar header={header} />
      <main style={{ flex: 1 }}>
        {screen === 1 && (
          <DataScreen header={header} onCalculate={handleCalculate} onReset={resetHeader => { setHeader(resetHeader); setRecommendations(null); setScreen(1) }} />
        )}
        {screen === 2 && recommendations && (
          <RecommendationsScreen
            data={recommendations}
            onSkuClick={handleSkuClick}
          />
        )}
        {screen === 2 && !recommendations && <div className="page muted">Загрузка рекомендаций…</div>}
        {screen === 3 && (
          <SkuScreen key={skuId} skuId={skuId} onBack={() => setScreen(2)} onSkuChange={setSkuId} />
        )}
        {screen === 4 && <ReviewScreen />}
        {screen === 5 && <ValidationScreen />}
      </main>
    </div>
  )
}

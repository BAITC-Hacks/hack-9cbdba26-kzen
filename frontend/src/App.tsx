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
  const [screen, setScreen] = useState<1 | 2 | 3 | 4 | 5>(1)
  const [skuId, setSkuId] = useState<SkuId | null>(null)
  const [header, setHeader] = useState<AppHeader | null>(null)
  const [recommendations, setRecommendations] = useState<RecommendationsPage | null>(null)

  useEffect(() => {
    getSession().then(setHeader)
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

  if (!header || !recommendations) {
    return (
      <div style={{ padding: 40, fontFamily: 'var(--font-body)', color: 'var(--color-neutral-600)' }}>
        Загрузка…
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopNav header={header} activeScreen={screen} onScreen={n => setScreen(n as 1 | 2 | 3 | 4 | 5)} />
      <ContextBar header={header} />
      <main style={{ flex: 1 }}>
        {screen === 1 && (
          <DataScreen header={header} onCalculate={handleCalculate} />
        )}
        {screen === 2 && (
          <RecommendationsScreen
            data={recommendations}
            onSkuClick={handleSkuClick}
          />
        )}
        {screen === 3 && (
          <SkuScreen skuId={skuId} onBack={() => setScreen(2)} />
        )}
        {screen === 4 && <ReviewScreen />}
        {screen === 5 && <ValidationScreen />}
      </main>
    </div>
  )
}

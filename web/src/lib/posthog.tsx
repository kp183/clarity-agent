'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { useEffect } from 'react'

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    posthog.init('phc_lSv1reY3rEYHEJx6YGWBWsLvscq0HNe0ANwzDhqMupd', {
      api_host: 'https://us.i.posthog.com',
      capture_pageview: true,
      capture_pageleave: true,
      autocapture: true,
    })
  }, [])

  return <PHProvider client={posthog}>{children}</PHProvider>
}

// Typed event tracker
export function track(event: string, properties?: Record<string, unknown>) {
  posthog.capture(event, properties)
}

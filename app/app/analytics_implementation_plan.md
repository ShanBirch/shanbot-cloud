# Shanbot Analytics Implementation Plan

## Overview
This document outlines the step-by-step process for implementing a comprehensive analytics system for Shanbot, covering data collection, processing, and visualization through the dashboard.

## Phase 1: Data Collection Structure

### Core Data Sources Integration
- [ ] ManyChat Webhook (`manychat_webhook_fullprompt.py`)
  - [ ] Message tracking
  - [ ] User identification
  - [ ] Conversation state tracking
  - [ ] Topic detection

- [ ] Instagram Bot (`followersbot2.py`)
  - [ ] Profile analysis collection
  - [ ] Message tracking
  - [ ] Engagement metrics
  - [ ] Story interactions

- [ ] Story Bot (`story1.py`)
  - [ ] Story interaction tracking
  - [ ] Response rates
  - [ ] Content analysis

- [ ] Check-in System (`checkin_current.py`)
  - [ ] Client progress tracking
  - [ ] Check-in completion rates
  - [ ] Performance metrics

### Data Collection Points

#### Message Events
- [ ] Sent messages tracking
- [ ] Received messages tracking
- [ ] Response time calculation
- [ ] Message content analysis

#### Instagram Profile Analysis
- [ ] Profile data extraction
- [ ] Content analysis
- [ ] Engagement history
- [ ] Interest categorization

#### Conversation Timing
- [ ] Start/end detection
- [ ] Duration tracking
- [ ] 24-hour conversation grouping
- [ ] Activity patterns

#### Topic Detection
- [ ] Keyword analysis
- [ ] Interest categorization
- [ ] Goal identification
- [ ] Sentiment analysis

#### Funnel Actions
- [ ] Meal plan offering tracking
- [ ] Link sharing detection
- [ ] Coaching inquiry identification
- [ ] Conversion tracking

#### Follow-up System
- [ ] Timing calculation
- [ ] Message generation
- [ ] Response tracking
- [ ] Effectiveness metrics

## Phase 2: Analytics Integration

### UnifiedAnalytics Class Implementation
```python
class UnifiedAnalytics:
    def __init__(self):
        self.conversation_data = {}
        self.global_metrics = {}
        self.instagram_profiles = {}
        self.follow_up_queue = {}
```

#### Core Methods
- [ ] Message tracking
- [ ] Profile data processing
- [ ] Conversation state management
- [ ] Funnel action tracking
- [ ] Follow-up management

#### Data Storage
- [ ] Optimized JSON structure
- [ ] Backup system
- [ ] Data validation
- [ ] Error handling

## Phase 3: Dashboard Implementation

### 1. Global Analytics
- [ ] Total Conversations Started
- [ ] Total Messages (Shannon/Leads)
- [ ] Response Rate Calculation
- [ ] Follow-up Message Tracking
- [ ] Coaching Inquiries Counter
- [ ] AI Detection System
- [ ] Average Response Time
- [ ] Messages per User
- [ ] Conversation End Detection

### 2. Responder Analysis
- [ ] Responder Categories
  - [ ] High Responder Logic
  - [ ] Medium Responder Logic
  - [ ] Low Responder Logic
  - [ ] No Responder Logic
- [ ] Interactive User List
- [ ] Category Filters
- [ ] Potential Client Detection

### 3. Topic Tracking
- [ ] Weight Loss Mentions
- [ ] Dietary Preferences
  - [ ] Vegan Detection
  - [ ] Vegetarian Detection
- [ ] Muscle Building Goals
- [ ] Mental Health Topics
- [ ] Coaching Interest
  - [ ] Online Coaching
  - [ ] Studio Coaching

### 4. Meal Plan Analytics
- [ ] Plan Offering Detection
  - [ ] Link Detection System
  - [ ] Plan Type Categorization
- [ ] Acceptance Tracking
- [ ] Type Distribution
- [ ] Goal Alignment

### 5. Conversation Interface
- [ ] User Selector
  - [ ] Active Status (Green)
  - [ ] Inactive Status (Red)
  - [ ] 24-hour Rule Implementation
- [ ] User Profile
  - [ ] Instagram Analysis Display
  - [ ] Membership Status
  - [ ] Engagement Metrics
- [ ] Conversation History
  - [ ] Timeline Display
  - [ ] Message Threading
  - [ ] Duration Tracking
- [ ] Topic Analysis
  - [ ] Interest Tracking
  - [ ] Goal Identification
- [ ] Funnel Position

### 6. Follow-up System
- [ ] Message Generation
  - [ ] Context Analysis
  - [ ] Personalization
- [ ] Timing System
  - [ ] Window Calculation
  - [ ] Optimal Time Selection
- [ ] Control Interface
  - [ ] Message Editor
  - [ ] Override Controls
  - [ ] Scheduling Options
- [ ] History Tracking

## Implementation Questions

1. **Conversation Timing**
   - How should multiple conversations within 24 hours be handled?
   - What defines a conversation end?

2. **Instagram Profile Analysis**
   - What specific data points should be extracted?
   - How should historical data be maintained?

3. **Dashboard Updates**
   - Real-time vs. On-demand refresh?
   - Update frequency requirements?

4. **Data Structure**
   - Keep existing or implement new structure?
   - Backup strategy?

## Progress Tracking

### Current Status
- Phase: Planning
- Next Steps: Awaiting confirmation and priority setting
- Blockers: None currently

### Completed Items
- [ ] Initial plan documentation
- [ ] System architecture design
- [ ] Component identification

### Next Actions
1. Confirm implementation approach
2. Set phase priorities
3. Begin implementation of chosen phase

## Notes
- Existing analytics file location: `C:\Users\Shannon\OneDrive\Desktop\shanbot\analytics_data.json`
- All scripts maintain existing functionality during updates
- Regular testing and validation throughout implementation 
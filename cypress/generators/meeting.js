import { DateTime } from 'luxon'
import { faker } from '@faker-js/faker'
import { random, startCase, times } from 'lodash-es'
import slugify from 'slugify'

import floorsMeta from '../fixtures/meeting-floors.json'

const xslugify = (str) => slugify(str.replace('/', '-'), { lower: true })

/**
 * Generate area response from label + children
 */
function createArea ({ label, children = [] }) {
  return {
    label,
    keyword: xslugify(label),
    toggled_by: [],
    is_bof: false,
    children: children.map(gr => {
      gr.toggled_by.push(xslugify(label))
      return gr
    })
  }
}

/**
 * Generate group response from label
 */
const uniqueGroupNames = []
function createGroup ({ label, mayBeBof = false, toggledBy = [] }) {
  // make sure group name is unique
  while (!label) {
    const nameAttempt = faker.word.verb()
    if (!uniqueGroupNames.includes(nameAttempt)) {
      label = nameAttempt
      uniqueGroupNames.push(nameAttempt)
    }
  }

  // Set toggledBy
  if (!toggledBy) {
    toggledBy = []
  }

  // 10% chance of BoF, if enabled
  const isBof = mayBeBof && random(0, 100) < 10
  if (isBof) {
    toggledBy.push('bof')
  }

  return {
    label,
    keyword: xslugify(label),
    toggled_by: toggledBy,
    is_bof: isBof
  }
}

/**
 * Generate event
 */
let lastEventId = 100000
let lastSessionId = 25000
function createEvent ({
  name = '',
  hasNote = false
}, floors, categories) {
  const floor = sample(floors)
  const room = sample(floor.rooms)
  const eventName = name ?? faker.lorem.sentence(random(2, 5))
  return {
    id: ++lastEventId,
    sessionId: ++lastSessionId,
    room: room.name,
    location: {
      short: floor.short,
      name: floor.name
    },
    acronym: "hackathon",
    duration: 41400,
    name: eventName,
    startDateTime: "2022-07-23T09:30:00",
    status: "sched",
    type: "other",
    isBoF: false,
    filterKeywords: [
      "coding",
      "hackathon",
      "hackathon-sessc"
    ],
    groupAcronym: "hackathon",
    groupName: "Hackathon",
    groupParent: {
      acronym: "gen"
    },
    note: hasNote ? faker.lorem.sentence(4) : '',
    remoteInstructions: '',
    flags: {
      agenda: false,
      showAgenda: false
    },
    agenda: {
      url: null
    },
    orderInMeeting: 1,
    short: "Hackathon",
    sessionToken: "sessc",
    links: {
      chat: "https://zulip.ietf.org/#narrow/stream/hackathon",
      chatArchive: "https://zulip.ietf.org/#narrow/stream/hackathon",
      recordings: [],
      videoStream: null,
      audioStream: null,
      webex: null,
      onsiteTool: null,
      calendar: `/meeting/123/session/${lastSessionId}.ics`
    }
  }
}

export default {
  /**
   * Generate a standard agenda data reponse
   */
  generateAgendaResponse ({ future = false, skipSchedule = false } = {}) {
    // Get random date but always start on a saturday
    const startDate = future ?
      DateTime.fromISO(faker.date.future(1).toISOString()).startOf('week').minus({ days: 2 }) :
      DateTime.fromISO(faker.date.past(5, DateTime.utc().minus({ months: 3 })).toISOString()).startOf('week').minus({ days: 2 })
    const endDate = startDate.plus({ days: 7 })

    // Generate floors
    const floors = times(6, (idx) => {
      const floorIdx = idx + 1
      const floor = floorsMeta[idx]
      return {
        id: floorIdx,
        image: `/media/floor/${floor.path}`,
        name: `Level ${startCase(faker.color.human())} ${floorIdx}`,
        short: `L${floorIdx}`,
        width: floor.width,
        height: floor.height,
        rooms: times(random(5, 10), (ridx) => {
          const roomName = `${faker.science.chemicalElement().name} ${floorIdx}-${ridx + 1}`
          // Keep 10% margin on each side
          const roomXUnit = Math.round(floor.width / 10)
          const roomYUnit = Math.round(floor.height / 10)
          const roomX = random(roomXUnit, roomXUnit * 8)
          const roomY = random(roomYUnit, roomYUnit * 8)
          return {
            id: floorIdx * 100 + ridx,
            name: roomName,
            functionalName: startCase(faker.lorem.words(2)),
            slug: xslugify(roomName),
            left: roomX,
            right: roomX + roomXUnit,
            top: roomY,
            bottom: roomY + roomYUnit
          }
        })
      }
    })

    // Generate categories (groups/areas)

    const categories = []

    if (!skipSchedule) {
      // Generate first group of areas
      const firstAreas = []
      const firstAreasNames = ['ABC', 'DEF', 'GHI', 'JKL', 'MNO', 'PQR', 'STU']
      for (const area of firstAreasNames) {
        firstAreas.push(createArea({
          label: area,
          children: times(random(2, 25), (idx) => {
            return createGroup({ mayBeBof: true })
          })
        }))
      }
      categories.push(firstAreas)

      // Generate second group of areas
      const secondAreas = []
      for (const area of ['UVW', 'XYZ0']) {
        secondAreas.push(createArea({
          label: area,
          children: times(random(2, 25), (idx) => {
            return createGroup({ mayBeBof: true })
          })
        }))
      }
      categories.push(secondAreas)

      // Generate last group of areas
      categories.push(
        [
          createArea({
            label: 'Administrative',
            children: [
              createGroup({ label: 'IETF Registration' })
            ]
          }),
          createArea({
            label: 'Coding',
            children: [
              createGroup({ label: 'Hackathon', toggledBy: ['hackathon'] }),
              createGroup({ label: 'Code Sprint', toggledBy: ['tools'] })
            ]
          }),
          createArea({
            label: 'Office hours',
            children: firstAreasNames.map(n => createGroup({ label: `${n} Office Hours`}))
          }),
          createArea({
            label: 'Open meeting',
            children: [
              createGroup({ label: 'WG Chairs Forum' }),
              createGroup({ label: `Newcomers' Feedback Session` })
            ]
          }),
          createArea({
            label: 'Plenary',
            children: [
              createGroup({ label: 'IETF Plenary', toggledBy: ['ietf'] })
            ]
          }),
          createArea({
            label: 'Presentation',
            children: [
              createGroup({ label: 'Hackathon Kickoff', toggledBy: ['hackathon'] }),
              createGroup({ label: 'Host Speaker Series', toggledBy: ['ietf'] }),
            ]
          }),
          createArea({
            label: 'Social',
            children: [
              createGroup({ label: `Newcomers' Quick Connections` }),
              createGroup({ label: 'Welcome Reception', toggledBy: ['ietf'] }),
              createGroup({ label: 'Break', toggledBy: ['secretariat'] }),
              createGroup({ label: 'Beverage and Snack Break', toggledBy: ['secretariat'] }),
              createGroup({ label: 'Hackdemo Happy Hour', toggledBy: ['hackathon'] })
            ]
          }),
          createArea({
            label: 'Tutorial',
            children: [
              createGroup({ label: `Tutorial: Newcomers' Overview` })
            ]
          }),
          createArea({
            label: '',
            children: [
              createGroup({ label: 'BoF' }),
              createGroup({ label: 'qwerty', toggledBy: ['abc'] }),
              createGroup({ label: 'azerty', toggledBy: ['def'] }),
              createGroup({ label: 'Tools' })
            ]
          })
        ]
      )
    }

    // Generate schedule

    const schedule = []

    if (!skipSchedule) {
      // Generate first 2 days (no regular sessions)



    }

    // Return response object

    return {
      meeting: {
        number: '123',
        city: faker.address.cityName(),
        startDate: startDate.toISODate(),
        endDate: endDate.toISODate(),
        updated: faker.date.between(startDate.toISO(), endDate.toISO()).toISOString(),
        timezone: 'Asia/Tokyo',
        infoNote: faker.lorem.paragraph(4),
        warningNote: ''
      },
      categories,
      isCurrentMeeting: future,
      useHedgeDoc: true,
      schedule,
      floors
    }
  }
}

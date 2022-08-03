import { DateTime } from 'luxon'
import { faker } from '@faker-js/faker'
import { random, startCase, times } from 'lodash-es'
import slugify from 'slugify'

import floorsMeta from '../fixtures/meeting-floors.json'

const xslugify = (str) =>  slugify(str.replace('/', '-'), { lower: true })

export default {
  generateAgendaResponse ({ future = false } = {}) {
    const startDate = future ? DateTime.fromISO(faker.date.future(1).toISOString()) : DateTime.fromISO(faker.date.past(5, DateTime.utc().minus({ months: 3 })).toISOString())
    const endDate = startDate.plus({ days: 7 })

    const floors = times(6, (idx) => {
      const floorIdx = idx + 1
      const floor = floorsMeta[idx]
      return {
        "id": floorIdx,
        "image": `/media/floor/${floor.path}`,
        "name": `Level ${startCase(faker.color.human())} ${floorIdx}`,
        "short": `L${floorIdx}`,
        "width": floor.width,
        "height": floor.height,
        "rooms": times(random(5, 10), (ridx) => {
          const roomName = `${faker.science.chemicalElement().name} ${floorIdx}-${ridx + 1}`
          // Keep 10% margin on each side
          const roomXUnit = Math.round(floor.width / 10)
          const roomYUnit = Math.round(floor.height / 10)
          const roomX = random(roomXUnit, roomXUnit * 8)
          const roomY = random(roomYUnit, roomYUnit * 8)
          return {
            "id": floorIdx * 100 + ridx,
            "name": roomName,
            "functionalName": startCase(faker.lorem.words(2)),
            "slug": xslugify(roomName),
            "left": roomX,
            "right": roomX + roomXUnit,
            "top": roomY,
            "bottom": roomY + roomYUnit
          }
        })
      }
    })

    const categories = [
      [],
      [],
      [
        {
          "label": "Plenary",
          "keyword": "plenary",
          "toggled_by": [],
          "is_bof": false,
          "children": [
            {
              "label": "IETF Plenary",
              "keyword": "ietf-plenary",
              "toggled_by": [
                "plenary",
                "ietf"
              ],
              "is_bof": false
            }
          ]
        },
      ]
    ]

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
      schedule: [],
      floors
    }
  }
}

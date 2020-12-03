import proj4 from 'proj4'
import { convertGeometryCoords } from '../../../../src/common/utils/gisUtils'

describe('GIS Utils', () => {
  it('Converts projection', async () => {
    const projection = 'PROJCS["NAD_1983_BC_Environment_Albers",' +
      'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",' +
      'SPHEROID["GRS_1980",6378137.0,298.257222101]],' +
      'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],' +
      'PROJECTION["Albers"],PARAMETER["False_Easting",1000000.0],' +
      'PARAMETER["False_Northing",0.0],' +
      'PARAMETER["Central_Meridian",-126.0],' +
      'PARAMETER["Standard_Parallel_1",50.0],' +
      'PARAMETER["Standard_Parallel_2",58.5],' +
      'PARAMETER["Latitude_Of_Origin",45.0],UNIT["Meter",1.0]]'

    const proj = proj4(projection)
    let geometry = {
      type: 'Point',
      coordinates: [1246130.5397275037, 467345.93477500137]
    }

    let convertedCoords
    convertedCoords = convertGeometryCoords(proj, geometry)

    expect(convertedCoords).toEqual([-122.62705496110696, 49.16967099034407])
  })
})

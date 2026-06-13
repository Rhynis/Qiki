export interface WardOption {
  name: string
  zone: 'Bình Thạnh' | 'Thủ Đức'
}

export interface DistrictOption {
  name: string
  wards: WardOption[]
}

export interface DeliveryWardGroup {
  name: WardOption['zone']
  wards: WardOption[]
}

export interface ProvinceOption {
  name: string
  wards: WardOption[]
}

export const DELIVERY_CITY = 'TP. Hồ Chí Minh'

export const deliveryWardGroups: DeliveryWardGroup[] = [
  {
    name: 'Bình Thạnh',
    wards: [
      { name: 'Bình Quới', zone: 'Bình Thạnh' },
      { name: 'Bình Lợi Trung', zone: 'Bình Thạnh' },
      { name: 'Gia Định', zone: 'Bình Thạnh' },
      { name: 'Thạnh Mỹ Tây', zone: 'Bình Thạnh' },
      { name: 'Bình Thạnh', zone: 'Bình Thạnh' },
    ],
  },
  {
    name: 'Thủ Đức',
    wards: [
      { name: 'Hiệp Bình', zone: 'Thủ Đức' },
      { name: 'Tam Bình', zone: 'Thủ Đức' },
      { name: 'Thủ Đức', zone: 'Thủ Đức' },
      { name: 'Linh Xuân', zone: 'Thủ Đức' },
    ],
  },
]

export const vietnameseAddresses: ProvinceOption[] = [
  {
    name: DELIVERY_CITY,
    wards: deliveryWardGroups.flatMap((group) => group.wards),
  },
]

export function getDistricts(_city: string): DistrictOption[] {
  return []
}

export function getWards(city: string, _district = ''): WardOption[] {
  if (city !== DELIVERY_CITY) return []
  return deliveryWardGroups.flatMap((group) => group.wards)
}

export function getDeliveryZoneByWard(ward: string): string | null {
  return getWards(DELIVERY_CITY).find((item) => item.name === ward)?.zone ?? null
}

export function isAllowedDeliveryWard(ward: string): boolean {
  return getDeliveryZoneByWard(ward) !== null
}

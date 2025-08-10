window.fetchProduct = async function(handle) {
  try {
    const response = await fetch(`/products/${handle}.js`)
    if (!response.ok) throw new Error('请求失败')
    const product = await response.json()
    return product
  } catch (error) {
    console.error(error)
    return null
  }
}
'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { ProductCard } from '@/components/ProductCard'
import { FiSearch, FiFilter } from 'react-icons/fi'

interface Product {
    id: string
    name: string
    slug: string
    description: string
    price: number
    image_url: string
    avg_rating: number
    review_count: number
}

interface Category {
    id: string
    name: string
    slug: string
}

function ProductsContent() {
    const searchParams = useSearchParams()
    const categoryFilter = searchParams.get('category')

    const [products, setProducts] = useState<Product[]>([])
    const [categories, setCategories] = useState<Category[]>([])
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    const [selectedCategory, setSelectedCategory] = useState(categoryFilter || '')
    const [sortBy, setSortBy] = useState('created_at')
    const [page, setPage] = useState(1)
    const [totalPages, setTotalPages] = useState(1)

    useEffect(() => {
        fetchCategories()
    }, [])

    useEffect(() => {
        fetchProducts()
    }, [selectedCategory, sortBy, page, search])

    async function fetchCategories() {
        try {
            const res = await fetch('/api/v1/categories')
            if (res.ok) {
                setCategories(await res.json())
            }
        } catch (error) {
            console.error('Failed to fetch categories')
        }
    }

    async function fetchProducts() {
        setLoading(true)
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '12',
                sort_by: sortBy,
            })
            if (selectedCategory) params.append('category_id', selectedCategory)
            if (search) params.append('search', search)

            const res = await fetch(`/api/v1/products?${params}`)
            if (res.ok) {
                const data = await res.json()
                setProducts(data.items || [])
                setTotalPages(data.pages || 1)
            }
        } catch (error) {
            console.error('Failed to fetch products')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-8">All Products</h1>

            {/* Filters */}
            <div className="flex flex-wrap gap-4 mb-8">
                {/* Search */}
                <div className="relative flex-1 min-w-[200px]">
                    <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search products..."
                        value={search}
                        onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                        className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                </div>

                {/* Category filter */}
                <select
                    value={selectedCategory}
                    onChange={(e) => { setSelectedCategory(e.target.value); setPage(1) }}
                    className="px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                    <option value="">All Categories</option>
                    {categories.map((cat) => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                </select>

                {/* Sort */}
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                    <option value="created_at">Newest</option>
                    <option value="price">Price: Low to High</option>
                    <option value="rating">Top Rated</option>
                    <option value="name">Name A-Z</option>
                </select>
            </div>

            {/* Products grid */}
            {loading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {[...Array(8)].map((_, i) => (
                        <div key={i} className="animate-pulse">
                            <div className="bg-gray-200 rounded-xl h-48 mb-4" />
                            <div className="bg-gray-200 h-4 rounded w-3/4 mb-2" />
                            <div className="bg-gray-200 h-4 rounded w-1/2" />
                        </div>
                    ))}
                </div>
            ) : products.length === 0 ? (
                <div className="text-center py-12">
                    <span className="text-6xl mb-4 block">🔍</span>
                    <h3 className="text-xl font-semibold text-gray-700">No products found</h3>
                    <p className="text-gray-500 mt-2">Try adjusting your search or filters</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {products.map((product) => (
                        <ProductCard key={product.id} product={product} />
                    ))}
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex justify-center gap-2 mt-8">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50"
                    >
                        Previous
                    </button>
                    <span className="px-4 py-2">
                        Page {page} of {totalPages}
                    </span>
                    <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="px-4 py-2 border border-gray-200 rounded-lg disabled:opacity-50"
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    )
}

// useSearchParams() needs a Suspense boundary so the page can be prerendered.
export default function ProductsPage() {
    return (
        <Suspense fallback={<div className="max-w-7xl mx-auto px-4 py-12 text-gray-500">Loading products...</div>}>
            <ProductsContent />
        </Suspense>
    )
}

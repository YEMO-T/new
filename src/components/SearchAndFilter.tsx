import React, { useState, useCallback } from 'react';
import './SearchAndFilter.css';

export interface FilterOptions {
  searchQuery: string;
  selectedCategory: string;
  sortBy: 'recent' | 'popular' | 'name' | 'rating';
  priceRange?: [number, number];
  tags?: string[];
}

interface SearchAndFilterProps {
  categories?: { id: string; name: string }[];
  tags?: string[];
  onFilterChange: (filters: FilterOptions) => void;
  showAdvanced?: boolean;
  placeholder?: string;
}

export const SearchAndFilter: React.FC<SearchAndFilterProps> = ({
  categories = [],
  tags = [],
  onFilterChange,
  showAdvanced = false,
  placeholder = '搜索...'
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [sortBy, setSortBy] = useState<'recent' | 'popular' | 'name' | 'rating'>('recent');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [showAdvancedFilter, setShowAdvancedFilter] = useState(showAdvanced);

  const handleFilterChange = useCallback(() => {
    onFilterChange({
      searchQuery,
      selectedCategory,
      sortBy,
      tags: selectedTags
    });
  }, [searchQuery, selectedCategory, sortBy, selectedTags, onFilterChange]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
  };

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
  };

  const handleSortChange = (sort: 'recent' | 'popular' | 'name' | 'rating') => {
    setSortBy(sort);
  };

  const handleTagToggle = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  const handleReset = () => {
    setSearchQuery('');
    setSelectedCategory('');
    setSortBy('recent');
    setSelectedTags([]);
  };

  React.useEffect(() => {
    handleFilterChange();
  }, [searchQuery, selectedCategory, sortBy, selectedTags, handleFilterChange]);

  return (
    <div className="search-and-filter">
      {/* 搜索栏 */}
      <div className="search-bar">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder={placeholder}
          className="search-input"
        />
        <span className="search-icon">🔍</span>
      </div>

      {/* 基础过滤器 */}
      <div className="basic-filters">
        {/* 排序 */}
        <div className="filter-item">
          <select
            value={sortBy}
            onChange={(e) => handleSortChange(e.target.value as any)}
            className="filter-select"
          >
            <option value="recent">最新</option>
            <option value="popular">最热</option>
            <option value="name">名称</option>
            <option value="rating">评分</option>
          </select>
        </div>

        {/* 分类 */}
        {categories.length > 0 && (
          <div className="filter-pills-group">
            <button
              className={`filter-pill ${selectedCategory === '' ? 'active' : ''}`}
              onClick={() => handleCategoryChange('')}
            >
              全部分类
            </button>
            {categories.map(cat => (
              <button
                key={cat.id}
                className={`filter-pill ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => handleCategoryChange(cat.id)}
              >
                {cat.name}
              </button>
            ))}
          </div>
        )}

        {/* 高级过滤器开关 */}
        {tags.length > 0 && (
          <button
            className="btn-advanced-filter"
            onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
          >
            {showAdvancedFilter ? '隐藏' : '显示'} 高级筛选
          </button>
        )}
      </div>

      {/* 高级过滤器 */}
      {showAdvancedFilter && tags.length > 0 && (
        <div className="advanced-filters">
          <div className="filter-group">
            <h4>标签</h4>
            <div className="tags-list">
              {tags.map(tag => (
                <button
                  key={tag}
                  className={`tag-button ${selectedTags.includes(tag) ? 'active' : ''}`}
                  onClick={() => handleTagToggle(tag)}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 活跃过滤器显示和重置 */}
      {(searchQuery || selectedCategory || selectedTags.length > 0) && (
        <div className="active-filters">
          <div className="active-items">
            {searchQuery && (
              <span className="active-filter-tag">
                搜索: {searchQuery}
              </span>
            )}
            {selectedCategory && (
              <span className="active-filter-tag">
                分类: {categories.find(c => c.id === selectedCategory)?.name}
              </span>
            )}
            {selectedTags.map(tag => (
              <span key={tag} className="active-filter-tag">
                {tag}
              </span>
            ))}
          </div>
          <button className="btn-reset" onClick={handleReset}>
            清除所有筛选
          </button>
        </div>
      )}
    </div>
  );
};

export default SearchAndFilter;

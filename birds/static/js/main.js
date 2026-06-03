// Bird Database - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize
    console.log('Bird Database loaded');
    
    // Load stats
    loadStats();
});

function loadStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            console.log('Database stats:', data);
        })
        .catch(error => console.error('Error loading stats:', error));
}

// Utility function to format bird name
function formatBirdName(name) {
    return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
}

// Export functions for use in templates
window.searchBirds = function() {
    const query = document.getElementById('searchInput').value;
    if (!query) {
        location.reload();
        return;
    }
    
    fetch(`/api/birds?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
            const list = document.getElementById('birdsList');
            if (data.length === 0) {
                list.innerHTML = '<p class="no-data">No birds found matching your search.</p>';
            } else {
                renderBirds(data, list);
            }
        })
        .catch(error => console.error('Search error:', error));
};

function renderBirds(birds, container) {
    container.innerHTML = birds.map((bird, idx) => `
        <div class="bird-card">
            <div class="bird-header">
                <h3>${bird.Name || 'Unknown'}</h3>
                <p class="species">${bird.Species || 'N/A'}</p>
            </div>
            <div class="bird-info">
                ${Object.entries(bird).filter(([k]) => !['Name', 'Species'].includes(k))
                    .map(([k, v]) => `<p><strong>${k}:</strong> ${v}</p>`).join('')}
            </div>
            <a href="/bird/${idx}" class="btn-details">View Details</a>
        </div>
    `).join('');
}

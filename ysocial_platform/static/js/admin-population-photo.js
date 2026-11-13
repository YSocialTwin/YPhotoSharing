/* Photo Sharing fields of the population-creation form: an optional section of the "Platform-specific fields" part.
 * It registers itself in the page (``YSocialPlatformSections``), which calls ``toggle`` when a switch changes, ``init``
 * once the page is ready and ``isValid`` before enabling the submit button.
 */
(function () {
  const PHOTO_FAVORITE_FILTER_DEFAULTS = [
      'warm',
      'vintage',
      'mono',
      'grain',
      'bright',
      'clean'
  ];
  const photoFavoriteFilters = new Set(PHOTO_FAVORITE_FILTER_DEFAULTS);
  const photoSelectedFavoriteFilters = new Set(PHOTO_FAVORITE_FILTER_DEFAULTS);

  function syncPhotoFavoriteFiltersField() {
      const hidden = document.getElementById('photo_favorite_filters');
      if (hidden) {
          hidden.value = JSON.stringify(Array.from(photoSelectedFavoriteFilters));
      }
  }

  function renderPhotoFavoriteFilters() {
      const container = document.getElementById('photo_favorite_filters_tags');
      if (!container) {
          return;
      }
      container.innerHTML = Array.from(photoFavoriteFilters).map(tag => {
          const active = photoSelectedFavoriteFilters.has(tag);
          return `
              <span class="profession-tag${active ? '' : ' inactive'}" data-filter-tag="${tag}" onclick="togglePhotoFavoriteFilterTag(this)">
                  ${tag}
              </span>
          `;
      }).join('');
      syncPhotoFavoriteFiltersField();
  }

  function togglePhotoFavoriteFilterTag(tagElement) {
      const tag = tagElement.dataset.filterTag;
      if (!tag) {
          return;
      }
      if (photoSelectedFavoriteFilters.has(tag)) {
          photoSelectedFavoriteFilters.delete(tag);
          tagElement.classList.add('inactive');
      } else {
          photoSelectedFavoriteFilters.add(tag);
          photoFavoriteFilters.add(tag);
          tagElement.classList.remove('inactive');
      }
      syncPhotoFavoriteFiltersField();
      validatePhotoSharingDistributions();
  }

  function addPhotoFavoriteFilter() {
      const input = document.getElementById('photo_favorite_filter_new');
      if (!input) {
          return;
      }
      const tag = input.value.trim().toLowerCase();
      if (!tag) {
          return;
      }
      photoFavoriteFilters.add(tag);
      photoSelectedFavoriteFilters.add(tag);
      input.value = '';
      renderPhotoFavoriteFilters();
      validatePhotoSharingDistributions();
  }

  function updatePhotoAttentionBudgetDistributionParams() {
      const distribution = document.getElementById('photo_attention_budget_distribution');
      const uniformParam = document.getElementById('photo_attention_budget_distribution_param');
      const geometricParam = document.getElementById('photo_attention_budget_distribution_param_geometric');
      const zipfParam = document.getElementById('photo_attention_budget_distribution_param_zipf');
      const poissonParams = document.getElementById('photo_attention_budget_poisson_params');
      const geometricParams = document.getElementById('photo_attention_budget_geometric_params');
      const zipfParams = document.getElementById('photo_attention_budget_zipf_params');
      if (!distribution || !uniformParam || !geometricParam || !zipfParam) {
          return;
      }

      poissonParams.style.display = 'none';
      geometricParams.style.display = 'none';
      zipfParams.style.display = 'none';
      uniformParam.disabled = true;
      geometricParam.disabled = true;
      zipfParam.disabled = true;

      switch (distribution.value) {
          case 'Poisson':
              poissonParams.style.display = 'block';
              uniformParam.disabled = false;
              break;
          case 'Geometric':
              geometricParams.style.display = 'block';
              geometricParam.disabled = false;
              uniformParam.value = geometricParam.value;
              break;
          case 'Zipf':
              zipfParams.style.display = 'block';
              zipfParam.disabled = false;
              uniformParam.value = zipfParam.value;
              break;
          default:
              uniformParam.disabled = false;
              break;
      }
  }

  function validatePhotoSharingDistributions() {
      const wrapper = document.getElementById('photo-sharing-config-wrapper');
      if (!wrapper || wrapper.classList.contains('d-none')) {
          return true;
      }

      const valuesFor = (ids) => ids.map(id => parseFloat((document.getElementById(id) || {}).value || '0') || 0);
      const storyTotal = valuesFor([
          'photo_story_public_percentage',
          'photo_story_followers_percentage',
          'photo_story_private_percentage'
      ]).reduce((sum, value) => sum + value, 0);
      const creatorTotal = valuesFor([
          'photo_creator_standard_percentage',
          'photo_creator_pro_percentage',
          'photo_creator_influencer_percentage'
      ]).reduce((sum, value) => sum + value, 0);

      const storyValidation = document.getElementById('photo_story_visibility_validation');
      const creatorValidation = document.getElementById('photo_creator_tier_validation');
      if (storyValidation) {
          storyValidation.style.display = Math.abs(storyTotal - 100) < 0.01 ? 'none' : 'block';
      }
      if (creatorValidation) {
          creatorValidation.style.display = Math.abs(creatorTotal - 100) < 0.01 ? 'none' : 'block';
      }

      return Math.abs(storyTotal - 100) < 0.01 &&
          Math.abs(creatorTotal - 100) < 0.01 &&
          photoSelectedFavoriteFilters.size > 0;
  }

  function photoSharingFormIsValid() {
      const wrapper = document.getElementById('photo-sharing-config-wrapper');
      if (!wrapper || wrapper.classList.contains('d-none')) {
          return true;
      }

      const minBudget = parseInt((document.getElementById('photo_attention_budget_min') || {}).value || '0', 10);
      const maxBudget = parseInt((document.getElementById('photo_attention_budget_max') || {}).value || '0', 10);
      if (Number.isNaN(minBudget) || Number.isNaN(maxBudget) || minBudget <= 0 || maxBudget <= 0 || minBudget > maxBudget) {
          return false;
      }
      return validatePhotoSharingDistributions();
  }

  function togglePhotoSharingSection() {
      const box = document.getElementById('include_photo_sharing');
      const wrapper = document.getElementById('photo-sharing-config-wrapper');
      if (!wrapper) {
          return;
      }
      const on = !!box && box.checked;
      wrapper.classList.toggle('d-none', !on);
      if (on) {
          renderPhotoFavoriteFilters();
          updatePhotoAttentionBudgetDistributionParams();
      }
      validatePhotoSharingDistributions();
  }

  function photoSharingSectionIsValid() {
      const valid = photoSharingFormIsValid();
      const wrapper = document.getElementById('photo-sharing-config-wrapper');
      const panel = document.getElementById('photo-sharing-config-panel');
      if (wrapper && !wrapper.classList.contains('d-none') && panel) {
          panel.style.borderColor = valid ? '#ddd' : '#fcc';
      }
      return valid;
  }

  const sections = (window.YSocialPlatformSections = window.YSocialPlatformSections || []);
  sections.push({
      toggle: togglePhotoSharingSection,
      init: renderPhotoFavoriteFilters,
      isValid: photoSharingSectionIsValid
  });

  Object.assign(window, {
      // the former name, kept for the pages and tests that still call it
      togglePhotoSharingConfigPanel: () => window.togglePlatformFields && window.togglePlatformFields(),
      togglePhotoFavoriteFilterTag,
      addPhotoFavoriteFilter,
      updatePhotoAttentionBudgetDistributionParams,
      validatePhotoSharingDistributions
  });
})();

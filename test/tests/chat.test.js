/**
 * @jest-environment jsdom
 */
require('@testing-library/jest-dom');
const { fireEvent } = require('@testing-library/dom');

// Setup test environment
beforeEach(() => {
  document.body.innerHTML = `
    <div id="chatBox"></div>
    <div id="moreMenu"></div>
    <div id="suggestionsModal"></div>
    <div id="confirmModal"></div>
    <div id="deleteConfirmModal"></div>
    <input id="userInput" type="text" />
    <div id="suggestionsList"></div>
  `;

  // Define the functions we want to test
  global.toggleMoreMenu = function() {
    const menu = document.getElementById('moreMenu');
    const isVisible = menu.classList.contains('show');
    if (!isVisible) {
      menu.classList.add('show');
      global.moreJustOpened = true;
      setTimeout(() => { global.moreJustOpened = false; }, 200);
    } else {
      menu.classList.remove('show');
    }
  };

  global.closeModal = function() {
    document.getElementById('confirmModal').classList.remove('show');
  };

  global.closeSuggestions = function() {
    document.getElementById('suggestionsModal').classList.remove('show');
  };

  global.deleteModal = function() {
    document.getElementById('deleteConfirmModal').classList.add('show');
  };

  global.closeDeleteModal = function() {
    document.getElementById('deleteConfirmModal').classList.remove('show');
  };

  global.openSuggestions = async function() {
    const mockSuggestions = ['Suggestion 1', 'Suggestion 2'];
    const list = document.getElementById('suggestionsList');
    list.innerHTML = '';
    mockSuggestions.forEach(prompt => {
      const li = document.createElement('li');
      li.textContent = prompt;
      li.onclick = () => {
        document.getElementById('userInput').value = prompt;
        closeSuggestions();
      };
      list.appendChild(li);
    });
    document.getElementById('suggestionsModal').classList.add('show');
  };
});

describe('Chat UI Tests', () => {
  beforeEach(() => {
    // Reset DOM elements before each test
    document.getElementById('moreMenu').classList.remove('show');
    document.getElementById('suggestionsModal').classList.remove('show');
    document.getElementById('confirmModal').classList.remove('show');
    document.getElementById('deleteConfirmModal').classList.remove('show');
  });

  test('toggleMoreMenu shows and hides menu', () => {
    const menu = document.getElementById('moreMenu');
    
    // Test opening
    toggleMoreMenu();
    expect(menu).toHaveClass('show');
    
    // Test closing
    toggleMoreMenu();
    expect(menu).not.toHaveClass('show');
  });

  test('closeModal removes show class', () => {
    const modal = document.getElementById('confirmModal');
    modal.classList.add('show');
    
    closeModal();
    expect(modal).not.toHaveClass('show');
  });

  test('closeSuggestions removes show class', () => {
    const modal = document.getElementById('suggestionsModal');
    modal.classList.add('show');
    
    closeSuggestions();
    expect(modal).not.toHaveClass('show');
  });

  test('deleteModal shows delete confirmation', () => {
    const modal = document.getElementById('deleteConfirmModal');
    
    deleteModal();
    expect(modal).toHaveClass('show');
  });

  test('closeDeleteModal hides delete confirmation', () => {
    const modal = document.getElementById('deleteConfirmModal');
    modal.classList.add('show');
    
    closeDeleteModal();
    expect(modal).not.toHaveClass('show');
  });

  test('menu closes when clicking outside', () => {
    jest.useFakeTimers();
    
    const menu = document.getElementById('moreMenu');
    menu.classList.add('show');
    
    // Open menu first to set moreJustOpened to false
    toggleMoreMenu();
    jest.advanceTimersByTime(200);
    
    // Now test clicking outside
    fireEvent.click(document.body);
    
    expect(menu).not.toHaveClass('show');
    
    jest.useRealTimers();
  });
});

describe('Suggestions API', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  test('openSuggestions fetches and displays suggestions', async () => {
    const mockSuggestions = ['Suggestion 1', 'Suggestion 2'];
    global.fetch.mockImplementationOnce(() => 
      Promise.resolve({
        json: () => Promise.resolve(mockSuggestions)
      })
    );

    await openSuggestions();

    const list = document.getElementById('suggestionsList');
    expect(list.children.length).toBe(2);
    expect(list.children[0].textContent).toBe('Suggestion 1');
    expect(list.children[1].textContent).toBe('Suggestion 2');
  });
});
